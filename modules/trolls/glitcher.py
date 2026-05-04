import ctypes, time, threading, random

def trigger_screen_glitch(duration=10):
    """
    Simulates a 'dying GPU' or 'glitch' effect by randomly shifting 
    blocks of the screen and inverting colors temporarily.
    """
    def _glitch():
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            hdc = user32.GetDC(0)
            
            end_time = time.time() + duration
            while time.time() < end_time:
                # Randomly choose an effect
                effect = random.randint(0, 2)
                
                if effect == 0:
                    # Shift a block
                    x1 = random.randint(0, w)
                    y1 = random.randint(0, h)
                    x2 = x1 + random.randint(-50, 50)
                    y2 = y1 + random.randint(-50, 50)
                    width = random.randint(100, 400)
                    height = random.randint(100, 400)
                    gdi32.BitBlt(hdc, x2, y2, width, height, hdc, x1, y1, 0x00CC0020) # SRCCOPY
                
                elif effect == 1:
                    # Invert a block
                    x = random.randint(0, w)
                    y = random.randint(0, h)
                    width = random.randint(50, 200)
                    height = random.randint(50, 200)
                    gdi32.BitBlt(hdc, x, y, width, height, hdc, x, y, 0x00550009) # DSTINVERT
                
                elif effect == 2:
                    # Draw random colored line/noise
                    x = random.randint(0, w)
                    y = random.randint(0, h)
                    for _ in range(5):
                        gdi32.SetPixel(hdc, x + random.randint(0, 10), y + random.randint(0, 10), random.randint(0, 0xFFFFFF))

                time.sleep(random.uniform(0.01, 0.05))
            
            user32.ReleaseDC(0, hdc)
            # Force a screen refresh to clear the mess
            user32.InvalidateRect(0, None, True)
        except: pass

    threading.Thread(target=_glitch, daemon=True).start()
