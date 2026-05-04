import ctypes

def block_mnk(enabled: bool):
    """Blocks all Mouse and Keyboard input (requires Admin)."""
    try:
        ctypes.windll.user32.BlockInput(enabled)
    except: pass
