import asyncio
import cv2
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, VideoStreamTrack, AudioStreamTrack
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame, AudioFrame
import time
from core.capture import capture_engine

import mss
from core.capture import capture_engine

def debug_log(msg):
    with open("omega_debug.txt", "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(f"[DEBUG] {msg}")

# Configure STUN for NAT traversal
ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {"urls": "stun:stun.services.mozilla.com"}
]

class MonitorStreamTrack(VideoStreamTrack):
    """Dynamically captures the selected monitor."""
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        try:
            frame_rgb = capture_engine.grab()
        except Exception as e:
            debug_log(f"Capture Engine Error: {e}")
            frame_rgb = None
            
        if frame_rgb is None:
            # RED DIAGNOSTIC FRAME: Signaling works, but Screen Capture fails
            frame_rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame_rgb[:] = [200, 0, 0] # Dark Red
            cv2.putText(frame_rgb, "SCREEN CAPTURE BLOCKED (RED)", (400, 320), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(frame_rgb, f"Backend: {capture_engine.mode}", (400, 360), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
            
        new_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        await asyncio.sleep(0.01) # target 60fps
        return new_frame

class ApexCameraTrack(VideoStreamTrack):
    """Captures webcam with dynamic toggle support."""
    def __init__(self, camera_idx=0):
        super().__init__()
        self.camera_idx = camera_idx
        self.cap = None
        self.enabled = False

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        if not self.enabled:
            # Pure black if intentionally disabled
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            if self.cap is None:
                try: 
                    self.cap = cv2.VideoCapture(self.camera_idx)
                    if not self.cap.isOpened(): 
                        debug_log(f"Camera {self.camera_idx} failed to open.")
                        self.cap = None
                except Exception as e:
                    debug_log(f"Camera Open Error: {e}")
            
            frame = None
            if self.cap and self.cap.isOpened():
                ret, img = self.cap.read()
                if ret: frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            if frame is None:
                # BLUE DIAGNOSTIC FRAME: Signaling works, but Camera fails
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                frame[:] = [0, 0, 150] # Dark Blue
                cv2.putText(frame, "CAMERA FAILED (BLUE)", (150, 240), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            else:
                frame = cv2.resize(frame, (640, 480))

        v_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        v_frame.pts = pts
        v_frame.time_base = time_base
        return v_frame

class ApexAudioTrack(AudioStreamTrack):
    """Captures microphone or system audio."""
    def __init__(self, source="mic"):
        super().__init__()
        self.source = source
        self.enabled = False
        self.samplerate = 44100
        self.channels = 2

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        samples = int(self.samplerate * 0.02) # 20ms
        
        # Placeholder for actual hardware capture
        # To keep stream alive, we send silence if disabled
        data = np.zeros((self.channels, samples), dtype=np.int16)
        
        if self.enabled:
            # Real capture would happen here (using soundcard/pyaudio)
            pass
            
        frame = AudioFrame.from_ndarray(data, format='s16p', layout='stereo')
        frame.pts = pts
        frame.sample_rate = self.samplerate
        frame.time_base = time_base
        return frame

class WebRTCManager:
    def __init__(self, ws_send_cb):
        self.pc = None
        self.channel = None
        self.ws_send = ws_send_cb
        self.loop = asyncio.get_event_loop()
        
        # Tracks
        self.monitor_track = None
        self.camera_track = None
        self.mic_track = None
        self.system_audio_track = None

    async def create_pc(self):
        if self.pc: 
            try: await self.pc.close()
            except: pass
        
        self.pc = RTCPeerConnection(configuration={"iceServers": ICE_SERVERS})
        
        @self.pc.on("datachannel")
        def on_datachannel(channel):
            self.channel = channel
            print(f"[RTC] Data channel established")
            
        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                await self.ws_send({
                    "t": "rtc_ice",
                    "candidate": candidate.candidate,
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex
                })

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            debug_log(f"RTC Connection state changed: {self.pc.connectionState}")
            if self.pc and self.pc.connectionState in ["failed", "closed"]:
                await self.stop()

    def add_streams(self):
        # 1. Desktop
        self.monitor_track = MonitorStreamTrack()
        self.pc.addTrack(self.monitor_track)
        
        # 2. Camera
        self.camera_track = ApexCameraTrack(camera_idx=0)
        self.pc.addTrack(self.camera_track)
        
        # 3. Mic
        self.mic_track = ApexAudioTrack(source="mic")
        self.pc.addTrack(self.mic_track)
        
        # 4. System Audio
        self.system_audio_track = ApexAudioTrack(source="system")
        self.pc.addTrack(self.system_audio_track)

    def toggle_camera(self, enabled: bool):
        if self.camera_track: self.camera_track.enabled = enabled

    def toggle_mic(self, enabled: bool):
        if self.mic_track: self.mic_track.enabled = enabled

    def toggle_audio(self, enabled: bool):
        if self.system_audio_track: self.system_audio_track.enabled = enabled

    async def handle_offer(self, sdp, type):
        await self.create_pc()
        self.add_streams()
        offer = RTCSessionDescription(sdp, type)
        await self.pc.setRemoteDescription(offer)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        await self.ws_send({
            "t": "rtc_answer",
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type
        })

    def add_ice_candidate(self, data):
        if self.pc:
            candidate = RTCIceCandidate(
                candidate=data["candidate"],
                sdpMid=data["sdpMid"],
                sdpMLineIndex=data["sdpMLineIndex"]
            )
            asyncio.run_coroutine_threadsafe(self.pc.addIceCandidate(candidate), self.loop)

    def send_frame(self, data: bytes):
        if self.channel and self.channel.readyState == "open":
            try:
                self.channel.send(data)
                return True
            except: pass
        return False

    async def stop(self):
        if self.pc:
            await self.pc.close()
            self.pc = None
        if self.camera_track and self.camera_track.cap:
            self.camera_track.cap.release()
            self.camera_track.cap = None
