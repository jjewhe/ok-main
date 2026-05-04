import os, threading, subprocess, tempfile, urllib.request

class JumpscareManager:
    """Native Performance Jumpscare Controller (No PyQt5)."""
    def __init__(self):
        self.is_running = False

    def start(self, image_url, sound_url=None):
        if self.is_running: return
        self.is_running = True
        threading.Thread(target=self._run_native, args=(image_url, sound_url), daemon=True).start()

    def stop(self):
        subprocess.run(["powershell", "-Command", "Get-Process | Where-Object {$_.MainWindowTitle -eq 'SYSTEM_ELITE_PRO'} | Stop-Process -Force"], capture_output=True)
        self.is_running = False

    def _run_native(self, image_url, sound_url):
        img_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        try:
            urllib.request.urlretrieve(image_url, img_temp)
        except: return

        if sound_url:
            def _play():
                try:
                    import pygame
                    pygame.mixer.init()
                    s_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                    urllib.request.urlretrieve(sound_url, s_temp)
                    pygame.mixer.music.load(s_temp)
                    pygame.mixer.music.play(-1)
                except:
                    try:
                        s_temp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
                        urllib.request.urlretrieve(sound_url, s_temp2)
                        import winsound
                        winsound.PlaySound(s_temp2, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
                    except: pass
            threading.Thread(target=_play, daemon=True).start()

        ps_script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        $img = [System.Drawing.Image]::FromFile('{img_temp}')
        $forms = @()
        foreach ($screen in [System.Windows.Forms.Screen]::AllScreens) {{
            $form = New-Object Windows.Forms.Form
            $form.Text = 'SYSTEM_ELITE_PRO'
            $form.FormBorderStyle = 'None'
            $form.StartPosition = 'Manual'
            $form.Location = $screen.Bounds.Location
            $form.Size = $screen.Bounds.Size
            $form.TopMost = $true
            $form.BackColor = 'Black'
            $pb = New-Object Windows.Forms.PictureBox
            $pb.Dock = 'Fill'
            $pb.Image = $img
            $pb.SizeMode = 'Zoom'
            $form.Controls.Add($pb)
            $form.Show()
            $forms += $form
        }}
        [System.Windows.Forms.Application]::Run()
        """
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        self.is_running = False

js_manager = JumpscareManager()
