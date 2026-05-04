import threading, time, os, tempfile, urllib.request, base64

def jumpscare_qt(image_input, sound_input=""):
    """
    Full-screen jumpscare on all monitors — PyQt5 powered.
    image_input and sound_input can be URLs or local file paths.
    """
    def _jumpscare():
        try:
            from PyQt5.QtWidgets import QApplication, QLabel
            from PyQt5.QtGui import QMovie, QPixmap
            from PyQt5.QtCore import Qt
            import pygame

            # Helper to resolve path (URL or Local)
            def resolve_path(inp, suffix):
                if not inp: return None
                if inp.startswith("http"):
                    fd, p = tempfile.mkstemp(suffix=suffix); os.close(fd)
                    urllib.request.urlretrieve(inp, p)
                    return p
                if os.path.exists(inp):
                    return inp
                # Check if it's base64 (very basic check)
                if len(inp) > 500:
                    try:
                        raw = base64.b64decode(inp.split(",")[-1])
                        fd, p = tempfile.mkstemp(suffix=suffix); os.write(fd, raw); os.close(fd)
                        return p
                    except: pass
                return None

            img_path = resolve_path(image_input, ".gif" if ".gif" in str(image_input).lower() else ".jpg")
            snd_path = resolve_path(sound_input, ".mp3")

            app = QApplication.instance() or QApplication([])
            screens = app.screens()
            labels, movies = [], []
            
            for screen in screens:
                rect = screen.geometry()
                lbl = QLabel()
                lbl.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
                lbl.setAttribute(Qt.WA_TranslucentBackground)
                lbl.setCursor(Qt.BlankCursor)
                lbl.setGeometry(rect)
                
                if img_path:
                    ext = img_path.lower()
                    if ext.endswith(".gif"):
                        mv = QMovie(img_path)
                        mv.setScaledSize(rect.size())
                        lbl.setMovie(mv)
                        mv.start()
                        movies.append(mv)
                    elif ext.endswith((".mp4", ".avi", ".mkv", ".mov")):
                        # Video fallback via OpenCV in a sub-thread for this specific label
                        def _vid_loop(label, path, r):
                            try:
                                import cv2, numpy as np
                                cap = cv2.VideoCapture(path)
                                while cap.isOpened() and time.time() < end:
                                    ret, frame = cap.read()
                                    if not ret: 
                                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # loop
                                        continue
                                    frame = cv2.resize(frame, (r.width(), r.height()))
                                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                    h, w, ch = frame.shape
                                    from PyQt5.QtGui import QImage
                                    qimg = QImage(frame.data, w, h, w * ch, QImage.Format_RGB888)
                                    label.setPixmap(QPixmap.fromImage(qimg))
                                    time.sleep(0.03)
                                cap.release()
                            except: pass
                        threading.Thread(target=_vid_loop, args=(lbl, img_path, rect), daemon=True).start()
                    else:
                        pix = QPixmap(img_path).scaled(rect.width(), rect.height(), Qt.KeepAspectRatioByExpanding)
                        lbl.setPixmap(pix)
                
                lbl.show()
                labels.append(lbl)
            
            if snd_path:
                try:
                    pygame.mixer.init()
                    pygame.mixer.music.load(snd_path)
                    pygame.mixer.music.play(-1)
                except: pass

            # Hold for 12 seconds (slightly longer)
            end = time.time() + 12
            while time.time() < end:
                app.processEvents()
                time.sleep(0.01)
            
            for lbl in labels: lbl.close()
            try:
                if pygame.mixer.get_init(): pygame.mixer.music.stop()
            except: pass
            
        except Exception as e:
            print(f"[JUMPSCARE_PRO] Error: {e}")

    threading.Thread(target=_jumpscare, daemon=True).start()
