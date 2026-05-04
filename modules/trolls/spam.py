import subprocess, time, webbrowser

def open_tabs_spam(url, count=10):
    """Opens a URL in multiple browser tabs."""
    for _ in range(min(count, 30)):
        webbrowser.open_new_tab(url)
        time.sleep(0.1)

def notepad_spam(count=5):
    """Opens multiple instances of Notepad."""
    for _ in range(count):
        subprocess.Popen(["notepad.exe"], creationflags=0x08000000)
        time.sleep(0.2)
