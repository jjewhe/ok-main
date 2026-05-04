import subprocess

def idiot_prank(start=True):
    """The 'You Are An Idiot' classic payload."""
    if not start:
        subprocess.run(["taskkill", "/F", "/IM", "iexplore.exe"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
        return
    
    ps_idiot = """
    $url = "https://youareanidiot.cc/"
    for($i=0; $i -lt 5; $i++) {
        Start-Process $url
        Start-Sleep -Milliseconds 500
    }
    """
    subprocess.Popen(["powershell", "-Command", ps_idiot], creationflags=0x08000000)
