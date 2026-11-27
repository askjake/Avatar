"""avatar_renderer.py - all Pillow drawing + animation state machine.

Tweak the look in the CONSTANTS block below. render() returns a 640x480 RGB numpy array.
"""
import math, random, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------- CONSTANTS YOU CAN TWEAK ----------------
# Scene is drawn at 640x480, then centred on a 16:9 canvas so Google Meet's 16:9 tile doesn't crop the head.
SCENE_W, SCENE_H = 640, 480
W, H = 960, 540                      # output frame size (16:9)
OFF_X, OFF_Y = (W - SCENE_W) // 2, (H - SCENE_H) // 2
HEAD_RX, HEAD_RY = 130, 150          # head half-width / half-height
HEAD_CENTER = (320, 225)
EYE_DX, EYE_DY = 55, -20             # eye offset from head centre
EYE_RX, EYE_RY = 24, 20              # eye size
MOUTH_Y = 80                         # mouth offset below head centre
MOUTH_HEIGHTS = [0, 8, 20, 35]       # px for levels 0..3
MOUTH_LERP = 0.3                     # per-frame smoothing toward target level
BOB_PX, BOB_PERIOD = 3, 4.0          # head bob
TILT_DEG = 2                         # max head tilt
EYE_TRACK_PX, EYE_TRACK_PERIOD = 4, 12.0
BLINK_INTERVAL = (3.0, 6.0)          # seconds between blinks
BLINK_HALF = 0.15                    # 150ms close, 150ms open
OUTLINE = (60, 40, 40)
# ---------------------------------------------------------


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _lerp(a, b, k):
    return a + (b - a) * k


class AvatarRenderer:
    def __init__(self, cfg):
        self.t0 = time.monotonic()
        self.mouth = 0.0           # smoothed mouth level (float 0..3)
        self.wide = 0.0            # attentive eye widening 0..1
        self.brow = 0.0            # eyebrow raise 0..1
        self.tilt = 0.0
        self.tilt_target = 0.0
        self.next_tilt = 8.0
        self.blink_start = None
        self.next_blink = random.uniform(*BLINK_INTERVAL)
        self.set_config(cfg)

    def set_config(self, cfg):
        self.skin = hex_rgb(cfg["skin"])
        self.hair = hex_rgb(cfg["hair"])
        self.name = cfg.get("name", "")
        self._make_background(hex_rgb(cfg["background"]))

    def _make_background(self, rgb):
        # soft vertical gradient: lighter at top -> chosen colour at bottom
        top = np.array([min(255, c + 35) for c in rgb], dtype=np.float32)
        bot = np.array(rgb, dtype=np.float32)
        k = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        arr = (top * (1 - k) + bot * k) * np.ones((H, W, 3), dtype=np.float32)
        self.bg = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")

    # ------------------------------------------------------------
    def render(self, level, listening=False):
        """Draw one frame. level = target mouth level 0..3 from the audio engine."""
        t = time.monotonic() - self.t0

        # ---- animation state ----
        self.mouth = _lerp(self.mouth, float(level), MOUTH_LERP)
        self.wide = _lerp(self.wide, 1.0 if level >= 2 else 0.0, 0.2)
        self.brow = _lerp(self.brow, 1.0 if listening else 0.0, 0.15)
        bob = math.sin(t * 2 * math.pi / BOB_PERIOD) * BOB_PX
        eye_x = math.sin(t * 2 * math.pi / EYE_TRACK_PERIOD) * EYE_TRACK_PX
        if t >= self.next_tilt:
            self.tilt_target = random.uniform(-TILT_DEG, TILT_DEG)
            self.next_tilt = t + random.uniform(8, 15)
        self.tilt = _lerp(self.tilt, self.tilt_target, 0.05)

        closure = 0.0  # 0 open .. 1 closed
        if self.blink_start is None and t >= self.next_blink:
            self.blink_start = t
        if self.blink_start is not None:
            e = t - self.blink_start
            if e < BLINK_HALF:
                closure = e / BLINK_HALF
            elif e < 2 * BLINK_HALF:
                closure = 1 - (e - BLINK_HALF) / BLINK_HALF
            else:
                self.blink_start = None
                self.next_blink = t + random.uniform(*BLINK_INTERVAL)

        # ---- drawing (back to front) ----
        face = Image.new("RGBA", (SCENE_W, SCENE_H), (0, 0, 0, 0))
        d = ImageDraw.Draw(face)
        cx, cy = HEAD_CENTER[0], HEAD_CENTER[1] + bob
        skin, hair = self.skin, self.hair

        # hair (back)
        d.ellipse((cx - HEAD_RX - 10, cy - HEAD_RY - 25, cx + HEAD_RX + 10, cy + 20), fill=hair)
        # ears
        for s in (-1, 1):
            ex = cx + s * (HEAD_RX + 2)
            d.ellipse((ex - 16, cy - 20, ex + 16, cy + 40), fill=skin, outline=OUTLINE, width=3)
        # head
        d.ellipse((cx - HEAD_RX, cy - HEAD_RY, cx + HEAD_RX, cy + HEAD_RY), fill=skin, outline=OUTLINE, width=3)
        # hair (fringe)
        d.polygon([(cx - 128, cy - 40), (cx - 120, cy - 110), (cx - 60, cy - 156), (cx + 60, cy - 156),
                   (cx + 120, cy - 110), (cx + 128, cy - 40), (cx + 90, cy - 95), (cx + 30, cy - 72),
                   (cx - 30, cy - 100), (cx - 90, cy - 80)], fill=hair)
        # cheeks + nose
        blush = tuple(min(255, c + 10) if i == 0 else max(0, c - 30) for i, c in enumerate(skin))
        for s in (-1, 1):
            d.ellipse((cx + s * 85 - 16, cy + 30, cx + s * 85 + 16, cy + 50), fill=blush)
        d.arc((cx - 10, cy + 10, cx + 10, cy + 40), 20, 160, fill=OUTLINE, width=3)

        # eyebrows (raise up to 7px when listening)
        by = cy - 68 - 7 * self.brow
        d.line((cx - 82, by + 5, cx - 34, by - 5), fill=hair, width=9)
        d.line((cx + 34, by - 5, cx + 82, by + 5), fill=hair, width=9)

        # eyes
        ery = EYE_RY * (1 + 0.15 * self.wide)
        for s in (-1, 1):
            ex, ey = cx + s * EYE_DX, cy + EYE_DY
            d.ellipse((ex - EYE_RX, ey - ery, ex + EYE_RX, ey + ery), fill="white", outline=OUTLINE, width=2)
            ix = ex + eye_x
            d.ellipse((ix - 12, ey - 12, ix + 12, ey + 12), fill=(70, 45, 30))     # iris
            d.ellipse((ix - 5, ey - 5, ix + 5, ey + 5), fill=(10, 10, 10))          # pupil
            d.ellipse((ix + 2, ey - 9, ix + 8, ey - 3), fill="white")               # sparkle
            if closure > 0:                                                         # eyelid slides down
                lid_bottom = ey - ery + 2 * ery * closure
                d.rectangle((ex - EYE_RX - 1, ey - ery - 2, ex + EYE_RX + 1, lid_bottom), fill=skin)
                d.line((ex - EYE_RX, lid_bottom, ex + EYE_RX, lid_bottom), fill=OUTLINE, width=3)

        # mouth
        mh = float(np.interp(self.mouth, [0, 1, 2, 3], MOUTH_HEIGHTS))
        my = cy + MOUTH_Y
        if mh < 3:
            d.arc((cx - 38, my - 22, cx + 38, my + 14), 20, 160, fill=OUTLINE, width=4)
        else:
            w = 52 + mh * 0.6
            top = my - 4
            d.ellipse((cx - w / 2, top, cx + w / 2, top + mh), fill=(70, 20, 30), outline=OUTLINE, width=3)
            th = min(9, mh * 0.3)
            d.rectangle((cx - w * 0.28, top + 3, cx + w * 0.28, top + 3 + th), fill="white")

        face = face.rotate(self.tilt, center=(cx, 300), resample=Image.BILINEAR)
        img = self.bg.copy()
        img.alpha_composite(face, (OFF_X, OFF_Y))

        # name badge
        if self.name:
            bd = ImageDraw.Draw(img)
            f = _font(26)
            tw = bd.textlength(self.name, font=f)
            bx0, bx1 = W / 2 - tw / 2 - 18, W / 2 + tw / 2 + 18
            bd.rounded_rectangle((bx0, H - 62, bx1, H - 18), radius=12, fill=(30, 40, 55, 255))
            bd.text((W / 2 - tw / 2, H - 56), self.name, font=f, fill="white")
        return np.asarray(img.convert("RGB"))


def make_icon(size=64, skin="#FDBCB4", hair="#4A2C17"):
    """Small face icon for the tray / .ico file."""
    s = size / 64.0
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((4 * s, 4 * s, 60 * s, 60 * s), fill=hex_rgb(hair))
    d.ellipse((7 * s, 12 * s, 57 * s, 60 * s), fill=hex_rgb(skin), outline=OUTLINE, width=max(1, int(2 * s)))
    d.pieslice((7 * s, 4 * s, 57 * s, 40 * s), 180, 360, fill=hex_rgb(hair))
    for x in (22, 42):
        d.ellipse(((x - 4) * s, 30 * s, (x + 4) * s, 38 * s), fill="white", outline=OUTLINE)
        d.ellipse(((x - 2) * s, 32 * s, (x + 2) * s, 36 * s), fill=(10, 10, 10))
    d.arc((20 * s, 38 * s, 44 * s, 54 * s), 20, 160, fill=OUTLINE, width=max(1, int(2 * s)))
    return im
