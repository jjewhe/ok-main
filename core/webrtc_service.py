import asyncio
import cv2
import numpy as np
import time

# ── aiortc imports with correct API ──────────────────────────────────────────
from aiortc import (RTCPeerConnection, RTCSessionDescription,
                    RTCConfiguration, RTCIceServer,
                    VideoStreamTrack, AudioStreamTrack, RTCRtpSender)
from av import VideoFrame, AudioFrame

from core.capture import capture_engine
from core.camera import camera_engine
from core.state import st

def debug_log(msg):
    with open("omega_debug.txt", "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(f"[DEBUG] {msg}")

# ── ICE server config using correct RTCConfiguration API ─────────────────────
def _make_ice_config():
    servers = [
        RTCIceServer(urls="stun:stun.l.google.com:19302"),
        RTCIceServer(urls="stun:stun1.l.google.com:19302"),
        RTCIceServer(urls="stun:stun.services.mozilla.com"),
        RTCIceServer(
            urls="turn:openrelay.metered.ca:80",
            username="openrelayproject",
            credential="openrelayproject"
        ),
        RTCIceServer(
            urls="turn:openrelay.metered.ca:443",
            username="openrelayproject",
            credential="openrelayproject"
        ),
    ]
    return RTCConfiguration(iceServers=servers)


class MonitorStreamTrack(VideoStreamTrack):
    """Dynamically captures the selected monitor via CaptureEngine."""
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        try:
            frame_rgb = capture_engine.grab() if hasattr(capture_engine, 'grab') else None
            if frame_rgb is not None:
                # Apex Ultra: Downscale before WebRTC H.264 encoding to massively reduce latency
                h, w = frame_rgb.shape[:2]
                if w > 1280:
                    frame_rgb = cv2.resize(frame_rgb, (1280, int(h * (1280 / w))), interpolation=cv2.INTER_NEAREST)
        except Exception as e:
            debug_log(f"Capture Engine Error: {e}")
            frame_rgb = None

        if frame_rgb is None:
            frame_rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame_rgb[:] = [200, 0, 0]
            cv2.putText(frame_rgb, "SCREEN CAPTURE BLOCKED (RED)", (400, 320),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        new_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        # Removed sleep — allow aiortc to pull frames at hardware speed
        return new_frame


class ApexCameraTrack(VideoStreamTrack):
    """Webcam with dynamic toggle support using CameraEngine."""
    def __init__(self, camera_idx=0):
        super().__init__()
        self.camera_idx = camera_idx
        self.enabled = False

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        frame = None
        if self.enabled and camera_engine:
            raw = camera_engine.get_raw_frame()
            if raw is not None:
                frame = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)

        if frame is None:
            # Fallback placeholder
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            if self.enabled:
                frame[:] = [0, 0, 150]
                cv2.putText(frame, "WAITING FOR CAMERA...", (150, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            else:
                frame[:] = [20, 20, 20]
                cv2.putText(frame, "CAMERA DISABLED", (180, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)

        v_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        v_frame.pts = pts
        v_frame.time_base = time_base
        return v_frame


class ApexAudioTrack(AudioStreamTrack):
    """Silent placeholder audio track to keep RTC stream alive."""
    def __init__(self, source="mic"):
        super().__init__()
        self.source = source
        self.enabled = False
        self.samplerate = 44100
        self.channels = 2

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        samples = int(self.samplerate * 0.02)  # 20ms block
        
        queue = st.mic_queue if self.source == "mic" else st.desktop_queue
        
        if not queue.empty():
            try:
                # Get one block from the queue
                data_raw = await queue.get()
                # data_raw is float32 [-1, 1] from sounddevice
                # Convert to int16 stereo
                if data_raw.ndim == 1:
                    data_raw = np.stack([data_raw, data_raw], axis=1)
                elif data_raw.shape[1] == 1:
                    data_raw = np.concatenate([data_raw, data_raw], axis=1)
                    
                data = (np.clip(data_raw, -1.0, 1.0) * 32767).astype(np.int16)
                # Reshape to (channels, samples) for 's16p' or keep (samples, channels) for 's16'
                # aiortc prefers planar 's16p' or interleaved 's16'. We'll use 's16' interleaved.
                frame = AudioFrame.from_ndarray(data.T, format='s16', layout='stereo')
            except:
                data = np.zeros((self.channels, samples), dtype=np.int16)
                frame = AudioFrame.from_ndarray(data, format='s16p', layout='stereo')
        else:
            # Silent filler
            data = np.zeros((self.channels, samples), dtype=np.int16)
            frame = AudioFrame.from_ndarray(data, format='s16p', layout='stereo')
            
        frame.pts = pts
        frame.sample_rate = self.samplerate
        frame.time_base = time_base
        return frame


class WebRTCManager:
    def __init__(self, ws_send_cb):
        self.pc     = None
        self.ws_send = ws_send_cb
        self.loop   = asyncio.get_event_loop()
        self.monitor_track      = None
        self.camera_track       = None
        self.mic_track          = None
        self.system_audio_track = None

    async def create_pc(self):
        if self.pc:
            try: await self.pc.close()
            except: pass

        self.pc = RTCPeerConnection(configuration=_make_ice_config())

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            debug_log(f"RTC Connection state: {self.pc.connectionState}")
            if self.pc and self.pc.connectionState in ("failed", "closed"):
                await self.stop()

        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                await self.ws_send({
                    "t": "rtc_ice",
                    "candidate": candidate.candidate,
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex
                })

    def add_streams(self):
        self.monitor_track      = MonitorStreamTrack()
        self.camera_track       = ApexCameraTrack(camera_idx=0)
        self.mic_track          = ApexAudioTrack(source="mic")
        self.system_audio_track = ApexAudioTrack(source="system")
        self.pc.addTrack(self.monitor_track)
        self.pc.addTrack(self.camera_track)
        self.pc.addTrack(self.mic_track)
        self.pc.addTrack(self.system_audio_track)

        # Force H.264 preference for 'fastest in the world' latency
        try:
            capabilities = RTCRtpSender.getCapabilities("video")
            if capabilities and capabilities.codecs:
                preferences = [c for c in capabilities.codecs if c.name == "H264"]
                if preferences:
                    for transceiver in self.pc.getTransceivers():
                        if transceiver.kind == "video":
                            try:
                                transceiver.setCodecPreferences(preferences)
                            except Exception as te:
                                debug_log(f"Transceiver setCodecPreferences Error: {te}")
        except Exception as e:
            debug_log(f"Codec Preference Error: {e}")

    def toggle_camera(self, enabled: bool):
        if self.camera_track: self.camera_track.enabled = enabled

    def toggle_mic(self, enabled: bool):
        if self.mic_track: self.mic_track.enabled = enabled

    def toggle_audio(self, enabled: bool):
        if self.system_audio_track: self.system_audio_track.enabled = enabled

    async def handle_offer(self, sdp, sdp_type):
        try:
            await self.create_pc()
            if not self.pc:
                debug_log("[RTC] Failed to create PeerConnection")
                return

            self.add_streams()
            
            # Use "offer" as default if sdp_type is missing
            stype = sdp_type if sdp_type else "offer"
            
            offer = RTCSessionDescription(sdp=sdp, type=stype)
            await self.pc.setRemoteDescription(offer)
            
            answer = await self.pc.createAnswer()
            if answer:
                await self.pc.setLocalDescription(answer)
                await self.ws_send({
                    "t":    "rtc_answer",
                    "sdp":  self.pc.localDescription.sdp,
                    "type": self.pc.localDescription.type
                })
        except Exception as e:
            debug_log(f"[RTC] handle_offer error: {e}")
            import traceback
            debug_log(traceback.format_exc())

    def add_ice_candidate(self, data):
        if not self.pc:
            return
        # ── FIXED: aiortc uses candidate_from_sdp, not RTCIceCandidate(candidate=...) ──
        try:
            from aiortc.sdp import candidate_from_sdp
            candidate_str = data.get("candidate", "")
            # JS sends "candidate:..." — strip the prefix
            if candidate_str.startswith("candidate:"):
                candidate_str = candidate_str[len("candidate:"):]
            if not candidate_str:
                return
            candidate = candidate_from_sdp(candidate_str)
            candidate.sdpMid        = data.get("sdpMid")
            candidate.sdpMLineIndex = data.get("sdpMLineIndex", 0)
            if self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.pc.addIceCandidate(candidate), self.loop)
        except Exception as e:
            debug_log(f"[RTC] ICE parse error: {e}")

    async def stop(self):
        if self.pc:
            try: await self.pc.close()
            except: pass
            self.pc = None
        if self.camera_track and self.camera_track.cap:
            self.camera_track.cap.release()
            self.camera_track.cap = None
