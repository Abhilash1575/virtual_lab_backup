import json
import asyncio
import fractions
import os
import sys

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
from av import AudioFrame
import time

# Add Audio directory to path for imports
AUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"Audio server starting from: {AUDIO_DIR}")

class SilenceAudioTrack(MediaStreamTrack):
    kind = "audio"

    async def recv(self):
        # Generate 20ms of silence at 48kHz
        samples = 960
        frame = AudioFrame(format="s16", layout="mono", samples=samples)
        for plane in frame.planes:
            plane.update(bytes(plane.buffer_size))

        pts, time_base = await self.next_timestamp()
        frame.pts = pts
        frame.sample_rate = 48000
        frame.time_base = time_base
        return frame

class AudioRestartManager:
    def __init__(self):
        self.restart_count = 0
        self.max_restarts = 3
        self.restart_delay = 2.0

    async def should_restart(self):
        if self.restart_count >= self.max_restarts:
            return False
        self.restart_count += 1
        await asyncio.sleep(self.restart_delay)
        return True

audio_restart_manager = AudioRestartManager()

pcs = set()

async def get_audio_track(pc):
    """Get audio track with fallback mechanisms using threading for better performance"""
    import concurrent.futures
    import threading

    def try_alsa_default():
        try:
            player = MediaPlayer("default", format="alsa")
            return player.audio
        except:
            return None

    def try_alsa_hw():
        try:
            options = {
                "format": "s16le",
                "rate": "48000",
                "channels": "2"
            }
            player = MediaPlayer("plughw:2,0", format="alsa", options=options)
            return player.audio
        except:
            return None

    def try_subprocess():
        try:
            import subprocess

            # Pipeline: arecord (stereo) -> ffmpeg (downmix to mono) -> MediaPlayer
            # 1. arecord: Capture Stereo (hw:2,0 requires 2 channels)
            cmd_arecord = ["arecord", "-D", "hw:2,0", "-c", "2", "-r", "48000", "-f", "S16_LE", "-t", "raw", "--buffer-time=5000"]
            proc_arecord = subprocess.Popen(cmd_arecord, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            # 2. ffmpeg: Downmix to Mono with low latency flags
            cmd_ffmpeg = [
                "ffmpeg",
                "-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "pipe:0",
                "-ac", "1", "-f", "s16le",
                "-fflags", "nobuffer", "-flags", "low_delay", "-fflags", "discardcorrupt",
                "-probesize", "32", "-analyzeduration", "0",
                "pipe:1"
            ]
            proc_ffmpeg = subprocess.Popen(cmd_ffmpeg, stdin=proc_arecord.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            # Store processes for cleanup
            pc.proc_arecord = proc_arecord
            pc.proc_ffmpeg = proc_ffmpeg

            # Allow proc_arecord to receive a SIGPIPE if proc_ffmpeg exits
            proc_arecord.stdout.close()

            # Start monitoring task for subprocess health
            asyncio.create_task(monitor_subprocesses(pc))

            player = MediaPlayer(
                proc_ffmpeg.stdout,
                format="s16le",
                options={
                    "sample_rate": "48000",
                    "channels": "1",
                    "fflags": "nobuffer",
                    "flags": "low_delay"
                }
            )
            return player.audio
        except:
            return None

    # Use threading to try audio sources concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(try_alsa_default),
            executor.submit(try_alsa_hw),
            executor.submit(try_subprocess)
        ]

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                print("Successfully obtained audio track")
                return result

    print("All audio sources failed, using silence.")
    return SilenceAudioTrack()

async def monitor_subprocesses(pc):
    """Monitor subprocess health and restart if needed"""
    while True:
        await asyncio.sleep(1)  # Check every second

        if hasattr(pc, 'proc_arecord') and pc.proc_arecord.poll() is not None:
            print(f"arecord process died with code {pc.proc_arecord.returncode}")
            # Process died, close connection to trigger cleanup
            pc.close()
            return

        if hasattr(pc, 'proc_ffmpeg') and pc.proc_ffmpeg.poll() is not None:
            print(f"ffmpeg process died with code {pc.proc_ffmpeg.returncode}")
            # Process died, close connection to trigger cleanup
            pc.close()
            return

        # Check if peer connection is still active
        if pc.connectionState in ['closed', 'failed']:
            return

async def index(request):
    client_path = os.path.join(AUDIO_DIR, "client.html")
    print(f"Serving client.html from: {client_path}")
    return web.FileResponse(client_path)

async def status(request):
    """Return audio server status"""
    audio_devices = []
    try:
        import subprocess
        result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
        audio_devices.append(result.stdout)
    except:
        audio_devices.append("Could not list audio devices")
    
    return web.json_response({
        "status": "running",
        "audio_dir": AUDIO_DIR,
        "active_connections": len(pcs),
        "audio_devices": audio_devices,
        "port": 9000
    })

async def offer(request):
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = web.Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_ice_state_change():
        print("ICE state:", pc.iceConnectionState)
        if pc.iceConnectionState in ["failed", "closed"]:
            # Terminate any running audio processes
            if hasattr(pc, 'proc_arecord') and pc.proc_arecord:
                pc.proc_arecord.terminate()
                pc.proc_arecord.wait()
            if hasattr(pc, 'proc_ffmpeg') and pc.proc_ffmpeg:
                pc.proc_ffmpeg.terminate()
                pc.proc_ffmpeg.wait()
            await pc.close()
            pcs.discard(pc)

    # Use microphone as audio source
    audio = await get_audio_track(pc)

    pc.addTrack(audio)

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    response = web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

async def cleanup(app):
    for pc in pcs:
        # Terminate any running audio processes
        if hasattr(pc, 'proc_arecord') and pc.proc_arecord:
            pc.proc_arecord.terminate()
            pc.proc_arecord.wait()
        if hasattr(pc, 'proc_ffmpeg') and pc.proc_ffmpeg:
            pc.proc_ffmpeg.terminate()
            pc.proc_ffmpeg.wait()
        await pc.close()

app = web.Application()
app.on_shutdown.append(cleanup)
app.router.add_get("/", index)
app.router.add_get("/status", status)
app.router.add_post("/offer", offer)
app.router.add_options("/offer", offer)  # Handle preflight OPTIONS

async def run_audio_server():
    await web._run_app(app, host="0.0.0.0", port=9000)

if __name__ == "__main__":
    asyncio.run(run_audio_server())
