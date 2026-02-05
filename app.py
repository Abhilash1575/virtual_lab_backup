#!/usr/bin/env python3
import eventlet
eventlet.monkey_patch()

import os, time, subprocess, threading, queue, tempfile, re, random, json, math, asyncio
from flask import Flask, send_from_directory, request, jsonify, render_template, abort, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, EmailField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Regexp
from flask_mail import Mail, Message
from dotenv import load_dotenv
from datetime import datetime, timedelta
import secrets

# Optional: serial usage guarded (so app still runs if pyserial not available)
try:
    import serial
    from serial.tools import list_ports
except Exception as e:
    serial = None
    list_ports = None

# Optional: GPIO usage for power control
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except Exception as e:
    GPIO = None
    GPIO_AVAILABLE = False

from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# Import database models
from models import db, User, Experiment, Session, Device, BookingSlot, EmailLog

# ---------- CONFIG ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # base path relative to script location
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
DEFAULT_FW_DIR = os.path.join(BASE_DIR, 'default_fw')  # contains esp32_default.bin etc
SOP_DIR = os.path.join(BASE_DIR, 'static')      # contains exp.pdf
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DEFAULT_FW_DIR, exist_ok=True)
os.makedirs(SOP_DIR, exist_ok=True)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'devkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///virtual_lab.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TIMEOUT_MINUTES'] = int(os.getenv('SESSION_TIMEOUT_MINUTES', 30))

# HTTPS Configuration
SSL_CERT_PATH = os.path.join(BASE_DIR, 'cert.pem')
SSL_KEY_PATH = os.path.join(BASE_DIR, 'key.pem')
USE_HTTPS = os.path.exists(SSL_CERT_PATH) and os.path.exists(SSL_KEY_PATH)

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('SMTP_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('SMTP_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('SMTP_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('FROM_EMAIL', 'noreply@virtuallab.com')

# Initialize Flask-Mail
mail = Mail(app)

# Initialize extensions
db.init_app(app)
socketio = SocketIO(app, async_mode='eventlet')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- FORMS ----------
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=150),
        Regexp(r'^[a-zA-Z0-9_]+$', message='Username can only contain letters, numbers, and underscores')
    ])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, max=128),
        Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]',
               message='Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, max=128),
        Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]',
               message='Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character')
    ])
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')

# Global active sessions for authorization
active_sessions = {}

# Power control GPIO pin
POWER_RELAY_PIN = 17

serial_lock = threading.Lock()
ser = None
ser_stop = threading.Event()
data_generator_thread = None  # global mock generator

# ---------- UTIL ----------
def list_serial_ports():
    if list_ports is None:
        return []
    return [p.device for p in list_ports.comports()]

# ---------- POWER CONTROL ----------
def init_power_control():
    """Initialize GPIO for power control"""
    if GPIO_AVAILABLE:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(POWER_RELAY_PIN, GPIO.OUT)
        GPIO.output(POWER_RELAY_PIN, GPIO.LOW)  # Start with power OFF
        print(f"[POWER] Initialized GPIO pin {POWER_RELAY_PIN} for power control")

def power_on():
    """Turn power supply ON"""
    if GPIO_AVAILABLE:
        GPIO.output(POWER_RELAY_PIN, GPIO.HIGH)
        print("[POWER] Power supply turned ON")
        return True
    else:
        print("[POWER] GPIO not available, cannot control power")
        return False

def power_off():
    """Turn power supply OFF"""
    if GPIO_AVAILABLE:
        GPIO.output(POWER_RELAY_PIN, GPIO.LOW)
        print("[POWER] Power supply turned OFF")
        return True
    else:
        print("[POWER] GPIO not available, cannot control power")
        return False

def cleanup_expired_sessions():
    """Clean up expired sessions and turn off power if no active sessions"""
    current_time = time.time()
    expired_keys = [k for k, v in active_sessions.items() if current_time > v['expires_at']]

    for k in expired_keys:
        print(f"[SESSION] Session {k} expired")
        del active_sessions[k]
        socketio.emit('power_status', {'status': 'off', 'session_key': k, 'reason': 'expired'})

    # If no active sessions remain, ensure power is off
    if not active_sessions:
        power_off()
        socketio.emit('power_status', {'status': 'off', 'reason': 'no_sessions'})

# ---------- EMAIL FUNCTIONS ----------
def send_email(recipient, subject, body, log_to_db=True):
    """Send email and optionally log to database"""
    try:
        msg = Message(subject=subject, recipients=[recipient], body=body)
        mail.send(msg)

        if log_to_db:
            email_log = EmailLog(recipient=recipient, subject=subject, body=body, status='sent')
            db.session.add(email_log)
            db.session.commit()

        print(f"[EMAIL] Sent to {recipient}: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send to {recipient}: {e}")

        if log_to_db:
            email_log = EmailLog(recipient=recipient, subject=subject, body=body,
                               status='failed', error_message=str(e))
            db.session.add(email_log)
            db.session.commit()

        return False

def send_booking_confirmation(booking_slot):
    """Send booking confirmation email"""
    user = booking_slot.user
    experiment = booking_slot.experiment

    subject = f"Booking Confirmed: {experiment.name}"
    body = f"""
Dear {user.username},

Your booking has been confirmed!

Experiment: {experiment.name}
Date & Time: {booking_slot.start_time.strftime('%Y-%m-%d %H:%M')} - {booking_slot.end_time.strftime('%H:%M')}
Duration: {experiment.duration_minutes} minutes

Please arrive 5 minutes before your scheduled time.
Make sure you have reviewed the experiment SOP before starting.

If you need to cancel or reschedule, please do so at least 2 hours in advance.

Best regards,
Virtual Lab Team
"""

    return send_email(user.email, subject, body.strip())

def send_session_reminder(session_obj, minutes_before=15):
    """Send session reminder email"""
    user = session_obj.user
    experiment = session_obj.experiment

    subject = f"Session Reminder: {experiment.name} in {minutes_before} minutes"
    body = f"""
Dear {user.username},

This is a reminder that your experiment session is starting in {minutes_before} minutes.

Experiment: {experiment.name}
Start Time: {session_obj.start_time.strftime('%Y-%m-%d %H:%M')}
Duration: {session_obj.duration_minutes} minutes

Please ensure you are ready and have reviewed the experiment procedures.

Best regards,
Virtual Lab Team
"""

    return send_email(user.email, subject, body.strip())

def schedule_session_reminders():
    """Background task to send session reminders"""
    while True:
        try:
            # Check for sessions starting in 15 minutes
            reminder_time = datetime.utcnow() + timedelta(minutes=15)
            upcoming_sessions = Session.query.filter(
                Session.start_time <= reminder_time,
                Session.start_time > datetime.utcnow(),
                Session.is_active == True
            ).all()

            for session_obj in upcoming_sessions:
                # Check if reminder already sent (you might want to add a field for this)
                send_session_reminder(session_obj)

        except Exception as e:
            print(f"[REMINDER] Error checking reminders: {e}")

        eventlet.sleep(300)  # Check every 5 minutes

# ---------- AUTHENTICATION ROUTES ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.check_password(form.password.data):
            if user.is_account_locked():
                flash('Account is locked due to too many failed login attempts. Try again later.', 'danger')
                return render_template('login.html', form=form)

            if user.is_password_expired():
                flash('Your password has expired. Please change your password.', 'warning')
                return redirect(url_for('change_password'))

            login_user(user, remember=form.remember.data)
            user.record_successful_login()

            next_page = request.args.get('next')
            db.session.commit()
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            if user:
                user.record_failed_login()
                db.session.commit()
            flash('Login unsuccessful. Please check username and password.', 'danger')

    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == form.username.data) | (User.email == form.email.data)
        ).first()

        if existing_user:
            if existing_user.username == form.username.data:
                flash('Username already exists. Please choose a different one.', 'danger')
            else:
                flash('Email already registered. Please use a different email.', 'danger')
            return render_template('register.html', form=form)

        # Create new user
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html', form=form)

        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Password changed successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's active sessions and recent bookings
    active_sessions = Session.query.filter_by(user_id=current_user.id, is_active=True).all()
    recent_bookings = BookingSlot.query.filter_by(user_id=current_user.id)\
        .order_by(BookingSlot.created_at.desc()).limit(5).all()

    return render_template('dashboard.html',
                         active_sessions=active_sessions,
                         recent_bookings=recent_bookings)

# ---------- ADMIN ROUTES ----------
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    # Get system statistics
    total_users = User.query.count()
    total_devices = Device.query.count()
    total_experiments = Experiment.query.count()
    active_sessions = Session.query.filter_by(is_active=True).count()

    # Recent activities
    recent_sessions = Session.query.order_by(Session.start_time.desc()).limit(10).all()
    recent_bookings = BookingSlot.query.order_by(BookingSlot.created_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_devices=total_devices,
                         total_experiments=total_experiments,
                         active_sessions=active_sessions,
                         recent_sessions=recent_sessions,
                         recent_bookings=recent_bookings)

@app.route('/admin/devices')
@login_required
def admin_devices():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    devices = Device.query.all()
    return render_template('admin/devices.html', devices=devices)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/experiments')
@login_required
def admin_experiments():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))

    experiments = Experiment.query.all()
    return render_template('admin/experiments.html', experiments=experiments)

@app.route('/admin/ota', methods=['GET', 'POST'])
@login_required
def admin_ota():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        update_file = request.files.get('update_file')
        update_type = request.form.get('update_type', 'package')

        if not update_file:
            flash('No update file selected.', 'danger')
            return redirect(request.url)

        # Save the update file
        filename = secure_filename(update_file.filename)
        update_path = os.path.join(UPLOAD_DIR, f"ota_{filename}")
        update_file.save(update_path)

        # Perform OTA update based on type
        success = perform_ota_update(update_path, update_type)

        if success:
            flash(f'OTA update ({update_type}) deployed successfully!', 'success')
            # Log the update
            print(f"[OTA] Update deployed: {filename} ({update_type})")
        else:
            flash('OTA update failed. Check system logs.', 'danger')

        return redirect(url_for('admin_ota'))

    return render_template('admin/ota.html')

def perform_ota_update(update_path, update_type):
    """Perform over-the-air system update"""
    try:
        if update_type == 'package':
            # For Debian packages
            cmd = f"sudo dpkg -i {update_path}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        elif update_type == 'system':
            # For system updates (apt packages)
            cmd = f"sudo apt-get install -y {update_path}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        elif update_type == 'firmware':
            # For firmware updates
            cmd = f"sudo cp {update_path} /lib/firmware/ && sudo update-initramfs -u"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        elif update_type == 'kernel':
            # For kernel updates (dangerous, requires restart)
            flash('Kernel updates require manual installation and system restart.', 'warning')
            return False

        else:
            flash('Unknown update type.', 'danger')
            return False

        if result.returncode == 0:
            print(f"[OTA] Update successful: {result.stdout}")
            return True
        else:
            print(f"[OTA] Update failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"[OTA] Error during update: {e}")
        return False

@app.route('/admin/system_status')
@login_required
def admin_system_status():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('admin_dashboard'))

    # Get system information
    try:
        # CPU usage
        cpu_result = subprocess.run(['top', '-bn1'], capture_output=True, text=True)
        cpu_lines = cpu_result.stdout.split('\n')
        cpu_usage = "Unknown"
        for line in cpu_lines:
            if 'Cpu(s)' in line:
                # Extract CPU usage percentage
                cpu_usage = line.split(',')[0].split(':')[1].strip()
                break

        # Memory usage
        mem_result = subprocess.run(['free', '-h'], capture_output=True, text=True)
        mem_lines = mem_result.stdout.split('\n')
        memory_info = mem_lines[1].split() if len(mem_lines) > 1 else ["Unknown"] * 7

        # Disk usage
        disk_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        disk_lines = disk_result.stdout.split('\n')
        disk_info = disk_lines[1].split() if len(disk_lines) > 1 else ["Unknown"] * 6

        # System uptime
        uptime_result = subprocess.run(['uptime', '-p'], capture_output=True, text=True)
        uptime = uptime_result.stdout.strip()

        # Active processes
        ps_result = subprocess.run(['ps', 'aux', '--no-headers'], capture_output=True, text=True)
        process_count = len(ps_result.stdout.strip().split('\n')) if ps_result.stdout.strip() else 0

    except Exception as e:
        cpu_usage = "Error"
        memory_info = ["Error"] * 7
        disk_info = ["Error"] * 6
        uptime = "Error"
        process_count = 0
        print(f"Error getting system status: {e}")

    return render_template('admin/system_status.html',
                         cpu_usage=cpu_usage,
                         memory_info=memory_info,
                         disk_info=disk_info,
                         uptime=uptime,
                         process_count=process_count)

@app.route('/experiments')
@login_required
def experiments_list():
    experiments = Experiment.query.filter_by(is_active=True).all()
    return render_template('experiments.html', experiments=experiments)

@app.route('/book_experiment/<int:experiment_id>', methods=['GET', 'POST'])
@login_required
def book_experiment(experiment_id):
    experiment = Experiment.query.get_or_404(experiment_id)

    if not experiment.is_active:
        flash('This experiment is not currently available.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Get booking parameters
        start_date = request.form.get('start_date')
        start_time = request.form.get('start_time')

        if not start_date or not start_time:
            flash('Please select a valid date and time.', 'danger')
            return render_template('book_experiment.html', experiment=experiment)

        try:
            # Parse date and time
            start_datetime = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M')
            end_datetime = start_datetime + timedelta(minutes=experiment.duration_minutes)

            # Check for conflicts
            conflicting_booking = BookingSlot.query.filter(
                BookingSlot.experiment_id == experiment_id,
                BookingSlot.status.in_(['available', 'booked']),
                BookingSlot.start_time < end_datetime,
                BookingSlot.end_time > start_datetime
            ).first()

            if conflicting_booking:
                flash('This time slot is already booked or unavailable. Please choose a different time.', 'danger')
                return render_template('book_experiment.html', experiment=experiment)

            # Create booking
            booking = BookingSlot(
                experiment_id=experiment_id,
                user_id=current_user.id,
                start_time=start_datetime,
                end_time=end_datetime,
                status='booked'
            )

            db.session.add(booking)
            db.session.commit()

            # Send confirmation email
            send_booking_confirmation(booking)

            flash('Booking confirmed! Check your email for details.', 'success')
            return redirect(url_for('dashboard'))

        except ValueError:
            flash('Invalid date/time format.', 'danger')
            return render_template('book_experiment.html', experiment=experiment)

    return render_template('book_experiment.html', experiment=experiment)

@app.route('/my_bookings')
@login_required
def my_bookings():
    bookings = BookingSlot.query.filter_by(user_id=current_user.id)\
        .order_by(BookingSlot.start_time.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/available_slots/<int:experiment_id>')
@login_required
def available_slots(experiment_id):
    experiment = Experiment.query.get_or_404(experiment_id)

    # Get all booking slots for the next 7 days
    start_date = datetime.utcnow().date()
    end_date = start_date + timedelta(days=7)

    slots = []
    current_time = datetime.combine(start_date, datetime.min.time())

    # Generate hourly slots for each day (9 AM to 5 PM)
    while current_time.date() <= end_date:
        if current_time.weekday() < 5:  # Monday to Friday
            slot_start = current_time.replace(hour=9, minute=0, second=0, microsecond=0)

            while slot_start.hour < 17:  # Until 5 PM
                slot_end = slot_start + timedelta(minutes=experiment.duration_minutes)

                # Check if slot conflicts with existing bookings
                conflicting_booking = BookingSlot.query.filter(
                    BookingSlot.experiment_id == experiment_id,
                    BookingSlot.status.in_(['booked']),
                    BookingSlot.start_time < slot_end,
                    BookingSlot.end_time > slot_start
                ).first()

                slots.append({
                    'start_time': slot_start,
                    'end_time': slot_end,
                    'available': conflicting_booking is None
                })

                slot_start += timedelta(hours=1)  # Next slot

        current_time += timedelta(days=1)

    return render_template('available_slots.html', experiment=experiment, slots=slots)

@app.route('/')
def index():
    return render_template('homepage.html')

@app.route('/experiment')
@login_required
def experiment():
    # Check if user already has an active session (single-user enforcement)
    active_user_sessions = [k for k, v in active_sessions.items()
                           if v.get('user_id') == current_user.id]

    if active_user_sessions:
        flash('You already have an active session. Please complete or end your current session first.', 'warning')
        return redirect(url_for('dashboard'))

    # Create new session key and database entry
    session_key = secrets.token_url_safe(32)

    # Create database session record
    experiment_obj = Experiment.query.filter_by(is_active=True).first()  # Get first active experiment
    if not experiment_obj:
        flash('No active experiments available.', 'danger')
        return redirect(url_for('dashboard'))

    db_session = Session(
        user_id=current_user.id,
        experiment_id=experiment_obj.id,
        session_key=session_key,
        duration_minutes=experiment_obj.duration_minutes,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    db.session.add(db_session)
    db.session.commit()

    # Add to active sessions
    active_sessions[session_key] = {
        'user_id': current_user.id,
        'start_time': time.time(),
        'duration': experiment_obj.duration_minutes,
        'expires_at': time.time() + (experiment_obj.duration_minutes * 60),
        'db_session_id': db_session.id
    }

    # Turn power ON when session starts
    power_on()
    socketio.emit('power_status', {'status': 'on', 'session_key': session_key})

    duration = active_sessions[session_key]['duration']
    session_end_time = int(active_sessions[session_key]['expires_at'] * 1000)  # JS milliseconds
    return render_template('index.html', session_duration=duration, session_end_time=session_end_time)

@app.route('/add_session', methods=['POST'])
def add_session():
    data = request.get_json()
    session_key = data.get('session_key')
    duration = data.get('duration', 5)
    if session_key:
        active_sessions[session_key] = {
            'start_time': time.time(),
            'duration': duration,
            'expires_at': time.time() + (duration * 60)
        }
        # Turn power ON when session starts
        power_on()
        socketio.emit('power_status', {'status': 'on', 'session_key': session_key})
    return jsonify({'status': 'added'})

@app.route('/remove_session', methods=['POST'])
def remove_session():
    data = request.get_json()
    session_key = data.get('session_key')
    if session_key in active_sessions:
        del active_sessions[session_key]
        # Turn power OFF when session ends
        power_off()
        socketio.emit('power_status', {'status': 'off', 'session_key': session_key})
    return jsonify({'status': 'removed'})

@app.route('/chart')
def chart():
    # Clean up expired sessions
    current_time = time.time()
    expired_keys = [k for k, v in active_sessions.items() if current_time > v['expires_at']]
    for k in expired_keys:
        del active_sessions[k]

    session_key = request.args.get('key')
    if not session_key or session_key not in active_sessions:
        return render_template('expired_session.html')
    return render_template('chart.html')

@app.route('/camera')
def camera():
    # Clean up expired sessions
    current_time = time.time()
    expired_keys = [k for k, v in active_sessions.items() if current_time > v['expires_at']]
    for k in expired_keys:
        del active_sessions[k]

    session_key = request.args.get('key')
    if not session_key or session_key not in active_sessions:
        return render_template('expired_session.html')
    return render_template('camera.html')

@app.route('/homepage')
def homepage():
    return render_template('homepage.html')

@app.route('/ports')
def ports_rest():
    return jsonify({'ports': list_serial_ports()})

# ---------- FLASH ----------
@app.route('/flash', methods=['POST'])
def flash():
    board = request.form.get('board', 'generic')
    port = request.form.get('port', '') or ''
    available_ports = list_serial_ports()
    default_port = available_ports[0] if available_ports else '/dev/ttyUSB0'
    port = port or default_port
    fw = request.files.get('firmware')
    if not fw:
        return jsonify({'status': 'No firmware uploaded'}), 400
    fname = secure_filename(fw.filename)
    dest = os.path.join(UPLOAD_DIR, fname)
    fw.save(dest)

    # Check if flash mode is requested
    flash_mode = request.form.get('flash_mode', 'false').lower() == 'true'

    commands = {
        'esp32': f"esptool.py --chip esp32 --port {port} write_flash 0x10000 {dest}",
        'esp8266': f"esptool.py --port {port} write_flash 0x00000 {dest}",
        'arduino': f"avrdude -v -p atmega328p -c arduino -P {port} -b115200 -D -U flash:w:{dest}:i",
        'attiny': f"avrdude -v -p attiny85 -c usbasp -P {port} -U flash:w:{dest}:i",
        'stm32': f"openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"program {dest} 0x08000000 verify reset exit\"",
        'nucleo_f446re': f"openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"program {dest} 0x08000000 verify reset exit\"",
        'black_pill': f"openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"program {dest} 0x08000000 verify reset exit\"",
        'msp430': f"mspdebug rf2500 'prog {dest}'",
        'tiva': f"openocd -f board/ti_ek-tm4c123gxl.cfg -c \"program {dest} verify reset exit\"",
        'tms320f28377s': f"python3 dsp/flash_tool.py {'--flash' if flash_mode else ''} {dest}".strip(),
        'generic': f"echo 'No flashing command configured for {board}. Uploaded to {dest}'"
    }

    cmd = commands.get(board, commands['generic'])
    socketio.start_background_task(run_flash_command, cmd, fname)
    return jsonify({'status': f'Flashing started for {board}', 'command': cmd})

def run_flash_command(cmd, filename=None):
    try:
        socketio.emit('flashing_status', f"Starting: {cmd}")
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(p.stdout.readline, ''):
            if line is None:
                continue
            socketio.emit('flashing_status', line.strip())
        p.wait()
        rc = p.returncode
        msg = '✅ Flashing completed successfully' if rc == 0 else f'⚠️ Flashing ended with return code {rc}'
        socketio.emit('flashing_status', f'{msg} (file: {filename})')
    except Exception as e:
        socketio.emit('flashing_status', f'Error while flashing: {e}')

# ---------- FACTORY RESET ENDPOINT ----------
# Expects JSON or form { "board": "esp32" }
# Finds corresponding default firmware file under DEFAULT_FW_DIR and calls run_flash_command
@app.route('/factory_reset', methods=['POST'])
def factory_reset():
    try:
        data = request.get_json(force=True)
    except:
        data = request.form.to_dict()
    board = (data.get('board') or 'generic').lower()

    # mapping from board -> default filename in DEFAULT_FW_DIR
    default_map = {
        'esp32': 'esp32_default.bin',
        'esp8266': 'esp32_default.bin',
        'arduino': 'arduino_default.hex',
        'attiny': 'attiny_default.hex',
        'stm32': 'stm32_default.bin',
        'nucleo_f446re': 'stm32_default.bin',
        'black_pill': 'stm32_default.bin',
        'msp430': 'generic_default.bin',
        'tiva': 'tiva_default.out',
        'tms320f28377s': 'tms320f28377s_default.out',
        'generic': 'generic_default.bin'
    }

    fname = default_map.get(board, default_map['generic'])
    fpath = os.path.join(DEFAULT_FW_DIR, fname)
    if not os.path.isfile(fpath):
        return jsonify({'error': f'Default firmware not found for board {board}: expected {fpath}'}), 404

    # choose command based on board (similar to /flash)
    port = request.args.get('port') or ''  # optional override
    available_ports = list_serial_ports()
    default_port = available_ports[0] if available_ports else '/dev/ttyUSB0'
    port = port or default_port
    commands = {
        'esp32': f"esptool.py --chip esp32 --port {port} write_flash 0x10000 {fpath}",
        'esp8266': f"esptool.py --port {port} write_flash 0x00000 {fpath}",
        'arduino': f"avrdude -v -p atmega328p -c arduino -P {port} -b115200 -D -U flash:w:{fpath}:i",
        'attiny': f"avrdude -v -p attiny85 -c usbasp -P {port} -U flash:w:{fpath}:i",
        'stm32': f"openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"program {fpath} 0x08000000 verify reset exit\"",
        'nucleo_f446re': f"openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"program {fpath} 0x08000000 verify reset exit\"",
        'black_pill': f"openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"program {fpath} 0x08000000 verify reset exit\"",
        'msp430': f"mspdebug rf2500 'prog {fpath}'",
        'tiva': f"openocd -f board/ti_ek-tm4c123gxl.cfg -c \"program {fpath} verify reset exit\"",
        'tms320f28377s': f"python3 dsp/flash_tool.py {fpath}",
        'generic': f"echo 'No flashing command configured for {board}. Default firmware at {fpath}'"
    }
    cmd = commands.get(board, commands['generic'])
    socketio.start_background_task(run_flash_command, cmd, fname)
    return jsonify({'status': f'Factory reset started for {board}', 'command': cmd})

# ---------- SOP DOWNLOAD ----------
# Serve SOP file(s) from static/sop directory. Example: GET /sop/exp.pdf
@app.route('/sop/<path:filename>')
def serve_sop(filename):
    # security: only allow files inside SOP_DIR
    safe_path = os.path.join(SOP_DIR, filename)
    if not os.path.isfile(safe_path):
        abort(404)
    return send_from_directory(SOP_DIR, filename, as_attachment=True)

# ---------- MOCK GENERATOR (disabled when serial is connected) ----------
def mock_data_generator():
    print("Mock data generator STARTED.")
    try:
        while True:
            # Use generic variable names instead of temp/humid
            sensor1 = 25.0 + random.uniform(-5.0, 5.0)
            sensor2 = 60.0 + random.uniform(-10.0, 10.0)
            sensor3 = 0.5 + random.uniform(-0.2, 0.2)
            sensor4 = 3.3 + random.uniform(-0.5, 0.5)
            payload = {
                'sensor1': round(sensor1, 2),
                'sensor2': round(sensor2, 2),
                'sensor3': round(sensor3, 3),
                'sensor4': round(sensor4, 2)
            }
            socketio.emit('sensor_data', payload)
            eventlet.sleep(0.1)  # faster update rate for smoother chart
    except eventlet.greenlet.GreenletExit:
        print("Mock data generator KILLED.")
    except Exception as e:
        print("Mock data generator error:", e)

# ---------- SERIAL READER ----------
def serial_reader_worker(serial_obj):
    try:
        while not ser_stop.is_set():
            line = serial_obj.readline()
            if not line:
                continue
            try:
                text = line.decode(errors='replace').strip()
            except:
                text = str(line)
            socketio.emit('feedback', text)

            # --- parse serial line into sensor_data for chart ---
            if any(sep in text for sep in [':', '=', '@', '>', '#', '^', '!', '$', '*', '%', '~', '\\', '|', '+', '-', ';', ',']) and any(c.isdigit() for c in text):
                # Flexible parsing similar to client-side
                trimmed = re.sub(r'^\d{1,2}:\d{2}:\d{2}\s*', '', text.strip())  # remove timestamp
                pairGroups = re.split(r'[,;]', trimmed)
                data = {}
                for group in pairGroups:
                    if not group.strip():
                        continue
                    normalized = re.sub(r'[:=>@#>^!$*~\\|+%\s&]+', ' ', group).strip()
                    tokens = re.split(r'\s+', normalized)
                    for i in range(0, len(tokens), 2):
                        if i + 1 < len(tokens):
                            k = tokens[i].strip().lower()
                            rawv = tokens[i + 1].strip()
                            try:
                                num = float(re.sub(r'[^\d\.\-+eE]', '', rawv))
                                if not math.isnan(num):
                                    data[k] = num
                            except:
                                pass
                # Keep original keys as sent by Arduino - no predefined mappings
                if data:
                    socketio.start_background_task(send_sensor_data_to_clients, data)
    except Exception as e:
        socketio.emit('feedback', f'[serial worker stopped] {e}')

# ---------- SOCKET HANDLERS ----------
@socketio.on('connect')
def on_connect():
    from flask import request
    print("[DEBUG] Client connected:", request.sid)
    emit('ports_list', list_serial_ports())
    emit('feedback', 'Server: socket connected')


@socketio.on('list_ports')
def handle_list_ports():
    emit('ports_list', list_serial_ports())

@socketio.on('connect_serial')
def handle_connect_serial(data):
    global ser, ser_stop, data_generator_thread
    port = data.get('port')
    baud = int(data.get('baud', 115200))
    if not port:
        emit('serial_status', {'status': 'error', 'message': 'No port selected'})
        return
    if serial is None:
        emit('serial_status', {'status': 'error', 'message': 'pyserial not available on server'})
        return
    with serial_lock:
        try:
            if ser and ser.is_open:
                ser.close()
            if data_generator_thread:
                data_generator_thread.kill()
                data_generator_thread = None

            ser = serial.Serial(port, baud, timeout=1)
            ser_stop.clear()
            # Use eventlet.spawn instead of threading.Thread
            eventlet.spawn(serial_reader_worker, ser)
            emit('serial_status', {'status': 'connected', 'port': port, 'baud': baud})
        except Exception as e:
            emit('serial_status', {'status': 'error', 'message': str(e)})

@socketio.on('disconnect_serial')
def handle_disconnect_serial():
    global ser, ser_stop, data_generator_thread
    with serial_lock:
        try:
            ser_stop.set()
            if ser and ser.is_open:
                ser.close()
            if data_generator_thread is None:
                data_generator_thread = eventlet.spawn(mock_data_generator)
            emit('serial_status', {'status': 'disconnected'})
        except Exception as e:
            emit('serial_status', {'status': 'error', 'message': str(e)})

@socketio.on('send_command')
def handle_send_command(data):
    global ser
    cmd = data.get('cmd', '')
    out = cmd + ("\n" if not cmd.endswith("\n") else "")
    try:
        with serial_lock:
            if ser and ser.is_open:
                ser.write(out.encode())
                emit('feedback', f'SENT> {cmd}')
            else:
                emit('feedback', f'[no-serial] {cmd}')
    except Exception as e:
        emit('feedback', f'[send error] {e}')

@socketio.on('waveform_config')
def handle_waveform_config(cfg):
    shape = cfg.get('shape'); freq = cfg.get('freq'); amp = cfg.get('amp')
    msg = f'WAVE {shape} FREQ {freq} AMP {amp}'
    emit('feedback', f'[waveform] {msg}')
    with serial_lock:
        try:
            if ser and ser.is_open:
                ser.write((msg + "\n").encode())
        except Exception as e:
            emit('feedback', f'[waveform send error] {e}')

def send_sensor_data_to_clients(data):
    try:
        with app.app_context():
            socketio.emit('sensor_data', data, namespace='/')
            print("[DEBUG] Emitted to clients:", data)
    except Exception as e:
        print("[ERROR] Failed to emit sensor_data:", e)


# ---------- MAIN ----------
if __name__ == '__main__':
    import socket
    def check_port(port, name):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            print(f"✓ {name} is running on port {port}")
            return True
        else:
            print(f"✗ {name} is NOT running on port {port}")
            return False
    
    print("========================================")
    print("Virtual Lab Server Starting...")
    print("=======================================")

    # Initialize database
    with app.app_context():
        db.create_all()

        # Create admin user if it doesn't exist
        admin_user = User.query.filter_by(username=os.getenv('ADMIN_USERNAME', 'admin')).first()
        if not admin_user:
            admin_user = User(
                username=os.getenv('ADMIN_USERNAME', 'admin'),
                email=os.getenv('ADMIN_EMAIL', 'admin@virtuallab.com'),
                role='admin'
            )
            admin_user.set_password(os.getenv('ADMIN_PASSWORD', 'ChangeMe123!'))
            db.session.add(admin_user)
            db.session.commit()
            print("✓ Admin user created")

        # Register this device
        import socket
        hostname = socket.gethostname()
        try:
            ip_address = socket.gethostbyname(hostname)
        except:
            ip_address = '127.0.0.1'

        device = Device.query.filter_by(hostname=hostname).first()
        if not device:
            device = Device(
                hostname=hostname,
                ip_address=ip_address,
                mac_address='00:00:00:00:00:00',  # Would need to get actual MAC
                device_type='raspberry_pi'
            )
            db.session.add(device)
            db.session.commit()
            print("✓ Device registered")

        # Create sample experiments if they don't exist
        if Experiment.query.count() == 0:
            experiments_data = [
                {
                    'name': 'DSP Signal Processing',
                    'description': 'Learn digital signal processing using TMS320F28377S DSP board',
                    'board_type': 'tms320f28377s',
                    'duration_minutes': 45,
                    'max_sessions': 1
                },
                {
                    'name': 'Arduino Microcontroller',
                    'description': 'Basic microcontroller programming and interfacing',
                    'board_type': 'arduino',
                    'duration_minutes': 30,
                    'max_sessions': 1
                },
                {
                    'name': 'ESP32 IoT Development',
                    'description': 'Internet of Things development with WiFi and Bluetooth',
                    'board_type': 'esp32',
                    'duration_minutes': 60,
                    'max_sessions': 1
                },
                {
                    'name': 'STM32 ARM Cortex-M',
                    'description': 'Advanced microcontroller development with ARM Cortex-M',
                    'board_type': 'stm32',
                    'duration_minutes': 45,
                    'max_sessions': 1
                }
            ]

            for exp_data in experiments_data:
                experiment = Experiment(**exp_data)
                db.session.add(experiment)

            db.session.commit()
            print("✓ Sample experiments created")

    # Initialize power control GPIO
    init_power_control()

    audio_running = check_port(9000, "Audio server")
    if not audio_running:
        print("\n⚠️  Audio service not detected!")
        print("   To enable audio, run:")
        print("   sudo systemctl enable audio_stream.service")
        print("   sudo systemctl start audio_stream.service"

    # Start session cleanup thread
    def session_cleanup_worker():
        while True:
            eventlet.sleep(30)  # Check every 30 seconds
            cleanup_expired_sessions()

    # Start email reminder scheduler
    eventlet.spawn(schedule_session_reminders)

    eventlet.spawn(session_cleanup_worker)

    port = 5000
    if USE_HTTPS:
        print(f"\n🔒 Starting HTTPS server on port {port}...")
        ssl_context = (SSL_CERT_PATH, SSL_KEY_PATH)
    else:
        print(f"\n⚠️  Starting HTTP server on port {port} (HTTPS certificates not found)")
        ssl_context = None

    print("=======================================")

    try:
        socketio.run(app, host='0.0.0.0', port=port, ssl_context=ssl_context)
    finally:
        # Cleanup GPIO on exit
        if GPIO_AVAILABLE:
            GPIO.cleanup()
        print("Main server stopped")
