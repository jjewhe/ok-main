import cv2
import numpy as np

class FilterEngine:
    def __init__(self):
        self.styles = {
            "Standard": self._none,
            "Negative": self._negative,
            "Grayscale": self._grayscale,
            "Sepia": self._sepia,
            "Matrix": self._matrix,
            "Terminal": self._terminal,
            "NightVision": self._night_vision,
            "Thermal": self._thermal,
            "Inferno": lambda f: self._apply_cmap(f, cv2.COLORMAP_INFERNO),
            "Plasma": lambda f: self._apply_cmap(f, cv2.COLORMAP_PLASMA),
            "Viridis": lambda f: self._apply_cmap(f, cv2.COLORMAP_VIRIDIS),
            "Magma": lambda f: self._apply_cmap(f, cv2.COLORMAP_MAGMA),
            "Ocean": lambda f: self._apply_cmap(f, cv2.COLORMAP_OCEAN),
            "Jet": lambda f: self._apply_cmap(f, cv2.COLORMAP_JET),
            "Turbo": lambda f: self._apply_cmap(f, cv2.COLORMAP_TURBO),
            "Cyberpunk": self._cyberpunk,
            "Retro8Bit": self._retro_8bit,
            "Glitch": self._glitch,
            "EdgeDetect": self._edge_detect,
            "Emboss": self._emboss,
            "Sketch": self._sketch,
            "Comic": self._comic,
            "Scanlines": self._scanlines,
            "Solarize": self._solarize,
            "Posterize": self._posterize,
        }
        # Add all other colormaps dynamically to reach 50+
        cmaps = {
            "Autumn": cv2.COLORMAP_AUTUMN, "Bone": cv2.COLORMAP_BONE, "Cividis": cv2.COLORMAP_CIVIDIS,
            "Cool": cv2.COLORMAP_COOL, "DeepGreen": cv2.COLORMAP_DEEPGREEN, "Hot": cv2.COLORMAP_HOT,
            "HSV": cv2.COLORMAP_HSV, "Parula": cv2.COLORMAP_PARULA, "Pink": cv2.COLORMAP_PINK,
            "Rainbow": cv2.COLORMAP_RAINBOW, "Spring": cv2.COLORMAP_SPRING, "Summer": cv2.COLORMAP_SUMMER,
            "Twilight": cv2.COLORMAP_TWILIGHT, "Winter": cv2.COLORMAP_WINTER
        }
        for name, code in cmaps.items():
            self.styles[name] = lambda f, c=code: self._apply_cmap(f, c)

    def apply(self, frame, style_name):
        if frame is None: return None
        func = self.styles.get(style_name, self._none)
        try:
            return func(frame)
        except:
            return frame

    def _none(self, frame): return frame

    def _negative(self, frame): return cv2.bitwise_not(frame)

    def _grayscale(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    def _sepia(self, frame):
        kernel = np.array([[0.393, 0.769, 0.189],
                          [0.349, 0.686, 0.168],
                          [0.272, 0.534, 0.131]])
        return cv2.transform(frame, kernel)

    def _apply_cmap(self, frame, cmap):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        colored = cv2.applyColorMap(gray, cmap)
        return cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)

    def _matrix(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        matrix = np.zeros_like(frame)
        matrix[:,:,1] = gray # Green channel only
        return matrix

    def _terminal(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        term = np.zeros_like(frame)
        term[:,:,0] = (gray * 1.0).astype(np.uint8) # R
        term[:,:,1] = (gray * 0.75).astype(np.uint8) # G
        return term

    def _night_vision(self, frame):
        # Green tint + Brightness boost + Noise
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        noise = np.random.randint(0, 50, gray.shape, dtype='uint8')
        nv = cv2.add(gray, noise)
        res = np.zeros_like(frame)
        res[:,:,1] = nv
        return res

    def _thermal(self, frame):
        return self._apply_cmap(frame, cv2.COLORMAP_JET)

    def _cyberpunk(self, frame):
        # High contrast, purple/cyan/neon
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        hsv[:,:,1] = cv2.multiply(hsv[:,:,1], 1.5)
        res = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        res[:,:,0] = cv2.add(res[:,:,0], 50) # Boost Red/Magenta
        res[:,:,2] = cv2.add(res[:,:,2], 30) # Boost Blue/Cyan
        return res

    def _retro_8bit(self, frame):
        h, w = frame.shape[:2]
        temp = cv2.resize(frame, (max(1, w//8), max(1, h//8)), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(temp, (w, h), interpolation=cv2.INTER_NEAREST)

    def _glitch(self, frame):
        # Shift channels
        res = frame.copy()
        rows, cols, _ = res.shape
        shift = 15
        if cols > shift:
            res[:, shift:] = frame[:, :-shift]
            res[:, :, 0] = frame[:, :, 0] # Red stays
            res[:, :, 1] = np.roll(frame[:, :, 1], shift, axis=1) # Green shifts
        return res

    def _edge_detect(self, frame):
        edges = cv2.Canny(frame, 100, 200)
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)

    def _emboss(self, frame):
        kernel = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]])
        return cv2.filter2D(frame, -1, kernel)

    def _sketch(self, frame):
        try:
            gray, color = cv2.pencilSketch(frame, sigma_s=60, sigma_r=0.07, shade_factor=0.05)
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        except: return frame

    def _comic(self, frame):
        try:
            return cv2.stylization(frame, sigma_s=60, sigma_r=0.07)
        except: return frame

    def _scanlines(self, frame):
        res = frame.copy()
        res[::2, :, :] = res[::2, :, :] // 2
        return res

    def _solarize(self, frame, threshold=128):
        return np.where(frame < threshold, frame, 255 - frame).astype(np.uint8)

    def _posterize(self, frame, bits=3):
        n = 2**bits
        return (frame // n * n).astype(np.uint8)

filter_engine = FilterEngine()
