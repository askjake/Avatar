"""Animate a portrait by resampling small regions of its original facial texture."""
import json
import math
import os
import random
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from avatar_renderer import AvatarRenderer, W, H, _font

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(HERE, "photos")
PROFILES_PATH = os.path.join(PHOTO_DIR, "profiles.json")

HEAD_PX = 390

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


class FeaturePatch:
    """Vertical inverse warp in a bounded patch, sampled from the neutral frame."""

    def __init__(self, rgb, center, rx, ry, slope):
        height, width = rgb.shape[:2]
        cx, cy = center
        extent = ry + abs(slope * rx)
        self.x = max(0, math.floor(cx - rx))
        self.y = max(0, math.floor(cy - extent))
        right = min(width, math.ceil(cx + rx) + 1)
        bottom = min(height, math.ceil(cy + extent) + 1)
        self.source = rgb[self.y:bottom, self.x:right]
        if self.source.size == 0:
            raise ValueError("Face landmark falls outside the head outline")
        rows, cols = np.indices(self.source.shape[:2], dtype=np.float32)
        dx = (cols + self.x - cx) / rx
        self.center = cy - self.y + slope * dx * rx
        self.dy = rows - self.center
        self.ry = ry
        self.cols = cols.astype(np.intp)
        taper = np.maximum(0, 1 - dx ** 2)
        self.weight = taper ** 2
        self.lid_weight = taper * (2 - taper)

    def sample(self, source_dy):
        rows = np.clip(self.center + source_dy, 0, self.source.shape[0] - 1)
        low = rows.astype(np.intp)
        frac = (rows - low)[..., None]
        high = np.minimum(low + 1, self.source.shape[0] - 1)
        return self.source[low, self.cols] * (1 - frac) + self.source[high, self.cols] * frac

    def mouth(self, amount):
        # Keep the photographed upper teeth fixed. Draw the lower lip down,
        # tapering to zero displacement at the cheeks and below the chin.
        gap = self.ry * 0.27 * amount * self.weight
        mapped = self.ry * (self.dy - gap) / (self.ry - gap)
        moved = np.where((self.dy > 0) & (self.dy < self.ry), mapped, self.dy)
        rgb = self.sample(moved)
        inside = np.clip(np.minimum(self.dy, gap - self.dy), 0, 1)[..., None]
        shade = self.sample(np.zeros_like(self.dy)) * (0.20, 0.12, 0.15)
        return (rgb * (1 - inside) + shade * inside).astype(np.uint8)

    def blink(self, closure):
        # Compress the visible eye into a narrowing slit while pulling the
        # actual upper and lower lid textures over it. Patch edges stay fixed.
        radius = self.ry * 0.49
        upper = -radius + 1.48 * radius * closure * self.lid_weight
        lower = radius - 0.49 * radius * closure * self.lid_weight
        dy = self.dy
        above = -self.ry + (dy + self.ry) * (self.ry - radius) / (upper + self.ry)
        slit = -radius + (dy - upper) * (2 * radius) / (lower - upper)
        below = radius + (dy - lower) * (self.ry - radius) / (self.ry - lower)
        mapped = np.where(dy < upper, above, np.where(dy > lower, below, slit))
        return self.sample(np.where(abs(dy) < self.ry, mapped, dy)).astype(np.uint8)


class PhotoAvatarRenderer(AvatarRenderer):
    def __init__(self, cfg):
        self.load_error = None
        self.closure = 0.0
        self.last_frame = 0.0
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

        self.head = head
        self.mask = mask.filter(ImageFilter.GaussianBlur(1.2))
        rgb = np.asarray(head.convert("RGB"))
        left_eye, right_eye = pt(prof["left_eye"]), pt(prof["right_eye"])
        dx = right_eye[0] - left_eye[0]
        dist = max(4, math.dist(left_eye, right_eye))
        slope = np.clip((right_eye[1] - left_eye[1]) / max(1, dx), -0.5, 0.5)
        self.lids = [FeaturePatch(rgb, eye, dist * 0.30, dist * 0.22, slope)
                     for eye in (left_eye, right_eye)]
        self.lips = FeaturePatch(rgb, pt(prof["mouth"]), max(4, prof["mouth_hw"] * s),
                                 dist * 0.68, slope)
        self.load_error = None

    def head_missing(self):
        return self.load_error is not None or not hasattr(self, "head")

    def render(self, level, listening=False):
        if self.head_missing():
            return super().render(level, listening)
        self._tick(level)
        head = self.head.copy()
        if self.mouth > 0.01:
            patch = self.lips
            head.paste(Image.fromarray(patch.mouth(self.mouth / 3)), (patch.x, patch.y))
        if self.closure > 0.01:
            for patch in self.lids:
                head.paste(Image.fromarray(patch.blink(self.closure)), (patch.x, patch.y))
        head.putalpha(self.mask)
        if abs(self.tilt) > 0.05:
            head = head.rotate(self.tilt, resample=Image.BICUBIC)
        img = self.bg.copy()
        img.alpha_composite(head, ((W - head.width) // 2,
                                   round((H - head.height) / 2 + self.bob)))
        self._badge(img)
        return np.asarray(img.convert("RGB"))

    def _tick(self, level):
        t = time.monotonic() - self.t0
        dt = max(0, t - self.last_frame)
        self.last_frame = t
        target = min(3.0, max(0.0, level))
        tau = 0.045 if target > self.mouth else 0.10
        self.mouth += (target - self.mouth) * -math.expm1(-dt / tau)
        self.bob = 1.2 * math.sin(t * 2 * math.pi / 4.3)
        self.tilt = 0.45 * math.sin(t * 2 * math.pi / 7.1)
        if self.blink_start is None and t >= self.next_blink:
            self.blink_start = t
        self.closure = 0.0
        if self.blink_start is not None:
            elapsed = t - self.blink_start
            if elapsed < 0.24:
                phase = min(elapsed / 0.085, (0.24 - elapsed) / 0.155)
                self.closure = phase * phase * (3 - 2 * phase)
            else:
                self.blink_start = None
                self.next_blink = t + random.uniform(3, 6)

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
