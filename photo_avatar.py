"""photo_avatar.py - South Park-style paper cut-out puppet built from a photo of your head.

How it works (all crude on purpose):
  * An ellipse around your head is cut out of the photo (white paper border + drop shadow).
  * The head is split at the mouth line into an UPPER part and a JAW flap.
  * Louder audio -> the jaw drops further; the gap shows a dark mouth with a strip of teeth.
  * Blink = a skin-coloured eyelid patch slides down over each eye.
  * Idle = head bob, small wobbly tilt. Talking = head bounces a little.

Your photos live in ./photos (git-ignored, never uploaded). Landmarks live in photos/profiles.json
and can be re-placed with Settings > "Set up face...".
"""
import json, math, os, random
import numpy as np
from PIL import Image, ImageDraw
from avatar_renderer import AvatarRenderer, W, H, _font, _lerp

try:
    import cv2
except Exception:  # opencv missing -> slower PIL fallback for the outline
    cv2 = None

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(HERE, "photos")
PROFILES_PATH = os.path.join(PHOTO_DIR, "profiles.json")

# ---------------- CONSTANTS YOU CAN TWEAK ----------------
HEAD_PX = 390                       # head height on the 540px-tall frame
JAW_OPEN_PX = [0, 9, 24, 42]        # jaw drop in pixels for mouth levels 0..3
BORDER_PX = 6                       # white paper-cutout border
SHADOW_OFFSET = (7, 9)
SHADOW_ALPHA = 110
MOUTH_DARK = (58, 14, 22)
TILT_DEG = 3                        # random wobble amount
BOUNCE_PX = 2.5                     # head bounce while talking
HEAD_BOB_PX = 4
# ---------------------------------------------------------

# Default landmarks, in pixels of the 672x900 photo copies. Eyes / mouth / head outline ellipse.
DEFAULT_PROFILES = {
    "bike": {"label": "Dirt bike", "file": "photos/head_bike.jpg",
             "left_eye": [228, 470], "right_eye": [310, 470],
             "mouth": [270, 556], "mouth_hw": 62,
             "top": 350, "chin": 640, "left": 152, "right": 352},
    "beanie": {"label": "Beanie", "file": "photos/head_beanie.jpg",
               "left_eye": [222, 441], "right_eye": [328, 447],
               "mouth": [272, 568], "mouth_hw": 68,
               "top": 253, "chin": 678, "left": 135, "right": 432},
}


def load_profiles():
    prof = json.loads(json.dumps(DEFAULT_PROFILES))
    try:
        with open(PROFILES_PATH, "r", encoding="utf-8") as f:
            for k, v in json.load(f).items():
                prof.setdefault(k, {}).update(v)
    except (OSError, ValueError):
        pass
    return prof


def save_profiles(profiles):
    os.makedirs(PHOTO_DIR, exist_ok=True)
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)


class PhotoAvatarRenderer(AvatarRenderer):
    def __init__(self, cfg):
        self.load_error = None
        super().__init__(cfg)           # sets timers, then calls set_config

    # ---------------------------------------------------- setup
    def set_config(self, cfg):
        super().set_config(cfg)
        self._load_head(cfg.get("photo", "bike"))

    def _load_head(self, key):
        profiles = load_profiles()
        prof = profiles.get(key) or next(iter(profiles.values()))
        path = os.path.join(HERE, prof["file"])
        try:
            img = Image.open(path).convert("RGB")
        except OSError as e:
            self.load_error = "photo not found: %s" % path
            print(self.load_error, e)
            return
        # --- cut the head out with an ellipse mask
        l, r, t, c = prof["left"], prof["right"], prof["top"], prof["chin"]
        pad = 3
        x0, y0, x1, y1 = int(l) - pad, int(t) - pad, int(r) + pad, int(c) + pad
        crop = img.crop((x0, y0, x1, y1))
        mask = Image.new("L", crop.size, 0)
        ImageDraw.Draw(mask).ellipse((pad, pad, crop.width - pad, crop.height - pad), fill=255)
        s = HEAD_PX / float(c - t)
        size = (max(2, int(crop.width * s)), max(2, int(crop.height * s)))
        crop = crop.resize(size, Image.LANCZOS)
        mask = mask.resize(size, Image.LANCZOS)
        head = crop.convert("RGBA")
        head.putalpha(mask)

        def pt(p):                      # photo coords -> scaled head coords
            return ((p[0] - x0) * s, (p[1] - y0) * s)

        self.hw, self.hh = head.size
        self.cut = int(min(max(pt(prof["mouth"])[1], 10), self.hh - 10))
        self.mcx = pt(prof["mouth"])[0]
        self.mhw = prof["mouth_hw"] * s
        self.eyes = [pt(prof["left_eye"]), pt(prof["right_eye"])]
        self.eye_dist = math.hypot(self.eyes[1][0] - self.eyes[0][0], self.eyes[1][1] - self.eyes[0][1])
        self.upper = head.crop((0, 0, self.hw, self.cut))
        self.jaw = head.crop((0, self.cut, self.hw, self.hh))
        self.strip = head.crop((0, self.cut - 2, self.hw, self.cut - 1))   # 1px row, stretched to fill the gap
        # lid colour = average skin just under the eyes
        arr = np.asarray(head.convert("RGB"))
        cols = []
        for ex, ey in self.eyes:
            yy = int(ey + 0.30 * self.eye_dist); xx = int(ex)
            cols.append(arr[max(0, yy - 3):yy + 4, max(0, xx - 3):xx + 4].reshape(-1, 3).mean(axis=0))
        self.lid = tuple(int(v) for v in np.mean(cols, axis=0))
        self.margin = BORDER_PX + 14
        self.load_error = None

    # ---------------------------------------------------- per-frame
    def render(self, level, listening=False):
        if self.head_missing():
            return super().render(level, listening)     # fall back to the cartoon face
        t = self._tick(level, listening)
        op = int(round(float(np.interp(self.mouth, [0, 1, 2, 3], JAW_OPEN_PX))))
        M = self.margin
        lw, lh = self.hw + 2 * M, self.hh + op + 2 * M
        layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))

        # upper head + blinking eyelids
        up = self.upper.copy()
        if self.closure > 0.04:
            d = ImageDraw.Draw(up)
            ew, eh = self.eye_dist * 0.30, self.eye_dist * 0.15
            for ex, ey in self.eyes:
                top = ey - eh * 1.3
                bottom = top + 2.7 * eh * self.closure
                d.ellipse((ex - ew * 1.15, top, ex + ew * 1.15, bottom), fill=self.lid)
                if self.closure > 0.5:
                    d.arc((ex - ew * 1.15, bottom - eh * 0.8, ex + ew * 1.15, bottom + 2), 20, 160,
                          fill=(45, 30, 25), width=3)
        layer.paste(up, (M, M), up)

        # gap between upper head and jaw = stretched cheek pixels + dark mouth + teeth
        if op > 0:
            gap = self.strip.resize((self.hw, op), Image.NEAREST)
            g = ImageDraw.Draw(gap)
            g.ellipse((self.mcx - self.mhw * 0.95, -op * 0.7, self.mcx + self.mhw * 0.95, op * 1.7), fill=MOUTH_DARK)
            th = min(op, max(3, int(op * 0.32)))
            g.rectangle((self.mcx - self.mhw * 0.62, 0, self.mcx + self.mhw * 0.62, th), fill=(246, 244, 236))
            layer.paste(gap, (M, M + self.cut), gap)
        layer.paste(self.jaw, (M, M + self.cut + op), self.jaw)

        # paper border + shadow
        alpha = np.asarray(layer.split()[3])
        k = 2 * BORDER_PX + 1
        if cv2 is not None:
            border = cv2.dilate(alpha, np.ones((k, k), np.uint8))
            shadow = cv2.GaussianBlur(border, (0, 0), 4)
        else:  # pragma: no cover
            from PIL import ImageFilter
            im = Image.fromarray(alpha).filter(ImageFilter.MaxFilter(k))
            border, shadow = np.asarray(im), np.asarray(im.filter(ImageFilter.GaussianBlur(4)))
        out = Image.new("RGBA", (lw + SHADOW_OFFSET[0], lh + SHADOW_OFFSET[1]), (0, 0, 0, 0))
        sh = Image.new("RGBA", (lw, lh), (0, 0, 0, 0)); sh.putalpha(Image.fromarray((shadow * SHADOW_ALPHA // 255).astype(np.uint8)))
        wh = Image.new("RGBA", (lw, lh), (255, 255, 255, 255)); wh.putalpha(Image.fromarray(border))
        out.alpha_composite(sh, SHADOW_OFFSET)
        out.alpha_composite(wh)
        out.alpha_composite(layer)
        if abs(self.tilt) > 0.05:
            out = out.rotate(self.tilt, resample=Image.BICUBIC, expand=True)

        img = self.bg.copy()
        px = int(W / 2 - out.width / 2)
        py = int(H / 2 - out.height / 2 + 6 + self.bob - self.mouth * BOUNCE_PX)
        img.paste(out, (px, py), out)
        self._badge(img)
        return np.asarray(img.convert("RGB"))

    def head_missing(self):
        return not hasattr(self, "upper") or self.load_error is not None

    def _tick(self, level, listening):
        """Advance mouth / blink / bob / tilt state (same timing rules as the cartoon face)."""
        import time
        t = time.monotonic() - self.t0
        self.mouth = _lerp(self.mouth, float(level), 0.3)
        self.bob = math.sin(t * 2 * math.pi / 4.0) * HEAD_BOB_PX
        if t >= self.next_tilt:
            self.tilt_target = random.uniform(-TILT_DEG, TILT_DEG)
            self.next_tilt = t + random.uniform(8, 15)
        self.tilt = _lerp(self.tilt, self.tilt_target, 0.05)
        # (tiny constant sway so it never looks frozen)
        self.tilt += math.sin(t * 2 * math.pi / 5.0) * 0.15
        closure = 0.0
        if self.blink_start is None and t >= self.next_blink:
            self.blink_start = t
        if self.blink_start is not None:
            e = t - self.blink_start
            if e < 0.15:
                closure = e / 0.15
            elif e < 0.30:
                closure = 1 - (e - 0.15) / 0.15
            else:
                self.blink_start = None
                self.next_blink = t + random.uniform(3.0, 6.0)
        self.closure = closure
        return t

    def _badge(self, img):
        if not self.name:
            return
        bd = ImageDraw.Draw(img)
        f = _font(26)
        tw = bd.textlength(self.name, font=f)
        bx0, bx1 = W / 2 - tw / 2 - 18, W / 2 + tw / 2 + 18
        bd.rounded_rectangle((bx0, H - 62, bx1, H - 18), radius=12, fill=(30, 40, 55, 255))
        bd.text((W / 2 - tw / 2, H - 56), self.name, font=f, fill="white")


def make_renderer(cfg):
    """Return the renderer for cfg['style'] ('cartoon' or 'photo'); falls back to cartoon on any error."""
    if cfg.get("style") == "photo":
        try:
            r = PhotoAvatarRenderer(cfg)
            if r.load_error is None:
                return r
            print("Photo style unavailable (%s) - using cartoon." % r.load_error)
        except Exception as e:
            print("Photo style failed (%s) - using cartoon." % e)
    return AvatarRenderer(cfg)
