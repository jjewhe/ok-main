import subprocess

def speak_tts(text: str):
    """Text-to-speech using built-in Windows SAPI (no external deps)."""
    try:
        # Method 1: PowerShell SAPI (most reliable)
        safe_text = text.replace('"', '').replace("'", "")[:500]
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f'Add-Type -AssemblyName System.Speech; '
             f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
             f'$s.Volume = 100; $s.Rate = 0; $s.Speak(\"{safe_text}\")'],
            timeout=30, creationflags=0x08000000, capture_output=True
        )
    except:
        try:
            # Method 2: COM object via ctypes
            import comtypes.client
            sapi = comtypes.client.CreateObject("SAPI.SpVoice")
            sapi.Speak(text)
        except: pass
