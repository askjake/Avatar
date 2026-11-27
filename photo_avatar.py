"""photo_avatar.py - South Park-style paper cut-out puppet built from a photo of your head.

How it works (all crude on purpose):
  * An ellipse around your head is cut out of the photo.
  * The cut-out is split just under your teeth into an UPPER head and a detached JAW piece.
  * Each piece is its own paper cut-out: white border + drop shadow. The jaw drops and swings
    on a hinge as you get louder; the gap shows a dark mouth (tongue + a hint of teeth), and
    the background shows through at the sides (no stretched pixels).
  * Blink = skin-coloured eyelid patch slides down over each eye.
  * Idle = head bob + wobbly tilt. Talking = head bounces a little.

Your photos live in ./photos (git-ignored, never uploaded). Landmarks live in photos/profiles.json
and can be re-placed with Settings > "Set up face...".
"""
import json, math, os, random, time
import numpy as np
from PIL import Image, ImageDraw, ImageChops
from avatar_renderer import AvatarRenderer, W, H, _font, _lerp

try:
    import cv2
except Exception:  # opencv missing -> slower PIL fallback for outlines
    cv2 = None

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(HERE, "photos")
PROFILES_PATH = os.path.join(PHOTO_DIR, "profiles.json")

# ---------------- CONSTANTS YOU CAN TWEAK ----------------
HEAD_PX = 390                       # head height on the 540px-tall frame
JAW_OPEN_PX = [0, 12, 28, 46]       # how far the jaw drops, mouth levels 0..3
JAW_SWING_DEG = 0.07                # extra hinge swing per pixel of drop (looks "flappy")
DETACH_MIN_PX = 3                   # below this the two pieces draw as one head (no seam)
BORDER_PX = 6                       # white paper-cutout border
SHADOW_OFFSET = (7, 9)
SHADOW_ALPHA = 110
MOUTH_DARK = (46, 10, 18, 255)      # inside of the mouth
TONGUE = (176, 62, 76, 255)
TEETH = (246, 244, 236, 255)
TILT_DEG = 3                        # random wobble amount
BOUNCE_PX = 2.5                     # head bounce while talking
HEAD_BOB_PX = 4
# ---------------------------------------------------------

# Default landmarks, in pixels of the 672x900 photo copies (photos/head_*.jpg).
# "mouth" = where the jaw is cut: just UNDER your teeth.
DEFAULT_PROFILES = {
    "bike": {"label": "Dirt bike", "file": "photos/head_bike.jpg",
             "left_eye": [228, 470], "right_eye": [310, 470],
             "mouth": [268, 563], "mouth_hw": 56,
             "top": 350, "chin": 640, "left": 152, "right": 352},
    "beanie": {"label": "Beanie", "file": "photos/head_beanie.jpg",
               "left_eye": [222, 441], "right_eye": [328, 447],
               "mouth": [268, 574], "mouth_hw": 52,
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


def _dilate(alpha, k):
    if cv2 is not None:
        return cv2.dilate(alpha, np.ones((k, k), np.uint8))
    from PIL import ImageFilter
    return np.asarray(Image.fromarray(alpha).filter(ImageFilter.MaxFilter(k)))


def _blur(a):
    if cv2 is not None:
        return cv2.GaussianBlur(a, (0, 0), 4)
    from PIL import ImageFilter
    return np.asarray(Image.fromarray(a).filter(ImageFilter.GaussianBlur(4)))


def _paper(layer):
    """(shadow, white_border) RGBA layers for one cut-out piece."""
    alpha = np.asarray(layer.split()[3])
    border = _dilate(alpha, 2 * BORDER_PX + 1)
    shadow = (_blur(border).astype(np.uint16) * SHADOW_ALPHA // 255).astype(np.uint8)
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0)); sh.putalpha(Image.fromarray(shadow))
    wh = Image.new("RGBA", layer.size, (255, 255, 255, 255)); wh.putalpha(Image.fromarray(border))
    return sh, wh


class PhotoAvatarRenderer(AvatarRenderer):
    def __init__(self, cfg):
        self.load_error = None
        self.closure = 0.0
        self.bob = 0.0
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
        arr = np.asarray(head.convert("RGB"))
        cols = []
        for ex, ey in self.eyes:
            yy = int(ey + 0.30 * self.eye_dist); xx = int(ex)
            cols.append(arr[max(0, yy - 3):yy + 4, max(0, xx - 3):xx + 4].reshape(-1, 3).mean(axis=0))
        self.lid = tuple(int(v) for v in np.mean(cols, axis=0))
        self.margin = BORDER_PX + 20
        self.load_error = None

    def head_missing(self):
        return not hasattr(self, "upper") or self.load_error is not None

    # ---------------------------------------------------- per-frame
    def _upper_with_lids(self):
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
        return up

    def _mouth_layer(self, size, op):
        """Dark mouth interior (tongue + a hint of teeth), clipped to a rounded shape between the pieces."""
        M = self.margin
        mw = max(self.mhw * 0.95, 20)
        y0 = M + self.cut - 8
        y1 = M + self.cut + op + 8
        box = (M + self.mcx - mw, y0, M + self.mcx + mw, y1)
        rad = max(2, min((y1 - y0) / 2.0, 26))
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle(box, radius=rad, fill=MOUTH_DARK)
        # tongue sits in the bottom of the mouth
        d.ellipse((M + self.mcx - mw * 0.5, y1 - (op * 0.6 + 6), M + self.mcx + mw * 0.5, y1 + 14), fill=TONGUE)
        # a hint of lower teeth riding on the jaw
        th = min(7, max(2, op * 0.18))
        d.rounded_rectangle((M + self.mcx - mw * 0.55, y1 - 8 - th, M + self.mcx + mw * 0.55, y1 - 8),
                            radius=2, fill=TEETH) if op > 20 else None
        clip = Image.new("L", size, 0)
        ImageDraw.Draw(clip).rounded_rectangle(box, radius=rad, fill=255)
        layer.putalpha(ImageChops.multiply(layer.split()[3], clip))
        return layer

    def render(self, level, listening=False):
        if self.head_missing():
            return super().render(level, listening)     # fall back to the cartoon face
        self._tick(level, listening)
        op = int(round(float(np.interp(self.mouth, [0, 1, 2, 3], JAW_OPEN_PX))))
        M = self.margin
        size = (self.hw + 2 * M + SHADOW_OFFSET[0], self.hh + op + 2 * M + SHADOW_OFFSET[1])
        up = self._upper_with_lids()
        up_layer = Image.new("RGBA", size, (0, 0, 0, 0)); up_layer.paste(up, (M, M), up)
        jaw_layer = Image.new("RGBA", size, (0, 0, 0, 0)); jaw_layer.paste(self.jaw, (M, M + self.cut + op), self.jaw)
        base = Image.new("RGBA", size, (0, 0, 0, 0))

        if op < DETACH_MIN_PX:
            # closed: one solid head, no seam
            merged = up_layer.copy(); merged.alpha_composite(jaw_layer)
            sh, wh = _paper(merged)
            base.alpha_composite(sh, SHADOW_OFFSET); base.alpha_composite(wh); base.alpha_composite(merged)
        else:
            # open: two separate paper pieces, jaw swings on a hinge under the head
            jaw_layer = jaw_layer.rotate(op * JAW_SWING_DEG, center=(M + self.hw / 2.0, M + self.cut + op),
                                         resample=Image.BICUBIC)
            pieces = [jaw_layer, up_layer]
            borders = []
            for lay in pieces:
                sh, wh = _paper(lay)
                base.alpha_composite(sh, SHADOW_OFFSET)
                borders.append(wh)
            for wh in borders:
                base.alpha_composite(wh)
            base.alpha_composite(self._mouth_layer(size, op))
            base.alpha_composite(jaw_layer)
            base.alpha_composite(up_layer)

        if abs(self.tilt) > 0.05:
            base = base.rotate(self.tilt, resample=Image.BICUBIC, expand=True)
        img = self.bg.copy()
        px = int(W / 2 - base.width / 2)
        py = int(H / 2 - base.height / 2 + 6 + self.bob - self.mouth * BOUNCE_PX)
        img.paste(base, (px, py), base)
        self._badge(img)
        return np.asarray(img.convert("RGB"))

    def _tick(self, level, listening):
        """Advance mouth / blink / bob / tilt state (same timing rules as the cartoon face)."""
        t = time.monotonic() - self.t0
        self.mouth = _lerp(self.mouth, float(level), 0.3)
        self.bob = math.sin(t * 2 * math.pi / 4.0) * HEAD_BOB_PX
        if t >= self.next_tilt:
            self.tilt_target = random.uniform(-TILT_DEG, TILT_DEG)
            self.next_tilt = t + random.uniform(8, 15)
        self.tilt = _lerp(self.tilt, self.tilt_target, 0.05)
        self.tilt += math.sin(t * 2 * math.pi / 5.0) * 0.15      # tiny constant sway so it never looks frozen
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
