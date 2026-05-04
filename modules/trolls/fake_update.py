import subprocess

def trigger_fake_update():
    """
    Triggers a full-screen, un-closable fake Windows Update screen.
    Uses the famous 'fakeupdate.net' or a local HTML implementation.
    """
    # Using the standard high-quality web-based fake update for best visuals
    # This also handles the 'hang' at 99% perfectly.
    # We use Microsoft Edge in 'app' mode (no address bar, no tabs) for a perfect disguise.
    url = "https://fakeupdate.net/win10ue/"
    
    # Flags to hide the window frame and taskbar entry as much as possible
    # --kiosk is best for full-screen locking
    cmd = [
        "msedge.exe",
        "--app=" + url,
        "--kiosk",
        "--no-first-run",
        "--no-default-browser-check"
    ]
    
    try:
        subprocess.Popen(cmd, creationflags=0x08000000)
    except:
        # Fallback to default browser if Edge is missing
        subprocess.Popen(["start", url], shell=True)
