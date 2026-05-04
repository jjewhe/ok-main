import subprocess

def set_volume(level: int):
    """Sets system volume level (0-100)."""
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        vol = devices.EndpointVolume
        vol.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100.0, None)
    except:
        # Fallback: PowerShell SAPI volume control
        subprocess.run(
            [
                "powershell",
                "-c",
                f"$obj = New-Object -ComObject WScript.Shell; 1..50 | % {{ $obj.SendKeys([char]174) }}; 1..([math]::Round({level}/2)) | % {{ $obj.SendKeys([char]175) }}",
            ],
            capture_output=True,
            creationflags=0x08000000,
        )
