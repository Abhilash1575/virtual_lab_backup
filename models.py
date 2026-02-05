from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import bcrypt

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), default='user')  # 'user' or 'admin'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    password_changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Password policy fields
    password_expires_at = db.Column(db.DateTime, nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        """Hash and set the password"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.password_changed_at = datetime.utcnow()
        self.password_expires_at = self.password_changed_at + timedelta(days=90)  # 90 days expiry
        self.failed_login_attempts = 0
        self.locked_until = None

    def check_password(self, password):
        """Check if password matches"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def is_password_expired(self):
        """Check if password has expired"""
        return datetime.utcnow() > self.password_expires_at

    def is_account_locked(self):
        """Check if account is locked"""
        if self.locked_until and datetime.utcnow() < self.locked_until:
            return True
        return False

    def record_failed_login(self):
        """Record a failed login attempt"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)  # Lock for 15 minutes

    def record_successful_login(self):
        """Record a successful login"""
        self.last_login = datetime.utcnow()
        self.failed_login_attempts = 0
        self.locked_until = None

class Experiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    board_type = db.Column(db.String(50), nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    max_sessions = db.Column(db.Integer, default=1)  # How many concurrent sessions allowed
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiment.id'), nullable=False)
    session_key = db.Column(db.String(64), unique=True, nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('sessions', lazy=True))
    experiment = db.relationship('Experiment', backref=db.backref('sessions', lazy=True))

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    mac_address = db.Column(db.String(17), unique=True, nullable=False)
    device_type = db.Column(db.String(50), default='raspberry_pi')
    location = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='online')  # 'online', 'offline', 'maintenance'
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BookingSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Null if available
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='available')  # 'available', 'booked', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)

    experiment = db.relationship('Experiment', backref=db.backref('booking_slots', lazy=True))
    user = db.relationship('User', backref=db.backref('bookings', lazy=True))

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='sent')  # 'sent', 'failed'
    error_message = db.Column(db.Text, nullable=True)