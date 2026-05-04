import subprocess
import os
import signal
import time

FFMPEG_PATH = os.path.join(os.getcwd(), "ffmpeg.exe")

class VideoEncoder:
    def __init__(self, width=1920, height=1080, fps=30, crf=23):
        self.width = width
        self.height = height
        self.fps = fps
        self.crf = crf
        self.process = None
        self._start_ffmpeg()

    def _start_ffmpeg(self):
        """Spawns ffmpeg to take raw RGB24 input from stdin and output H.264 NAL units to stdout"""
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "-", # Stdin input
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-crf", str(self.crf),
            "-g", "30", # Intra-frame interval
            "-bf", "0", # No B-frames
            "-f", "h264",
            "-" # Stdout output
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )
            print(f"[Encoder] FFmpeg pipeline started: {self.width}x{self.height} @ {self.fps}FPS")
        except Exception as e:
            print(f"[Encoder] FFmpeg critical error: {e}")

    def encode(self, frame_bytes):
        """Pushes raw pixel bytes into ffmpeg and retrieves the H.264 NAL bucket"""
        if not self.process: return None
        try:
            self.process.stdin.write(frame_bytes)
            self.process.stdin.flush()
            # This is tricky as we need to read exactly one frame's worth of H.264 data
            # Typically, we just read whatever is available in the pipe
            # For H.264 over a pipe, we can read until we find a full frame. 
            # Simplified approach: read 2048 bytes or similar. 
            # Reality: aiortc/webrtc will handle the framing better.
            return self.process.stdout.read(4096) 
        except:
            return None

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None

video_encoder = None # Initialized on demand in the stream loop
