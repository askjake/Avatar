"""config.py - load/save avatarcam_settings.json (lives next to this file)."""
import json, os

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatarcam_settings.json")

# ---- Preset swatches shown in the settings window (edit freely) ----
SKIN_PRESETS = ["#FDBCB4", "#F1C27D", "#E0AC69", "#C68642", "#8D5524"]
HAIR_PRESETS = ["#4A2C17", "#1B1B1B", "#B5651D", "#E6C27A", "#B03A2E"]

DEFAULTS = {
    "name": "",
    "skin": SKIN_PRESETS[0],
    "hair": HAIR_PRESETS[0],
    "background": "#9FB4C7",   # soft blue-grey
    "mic_device": None,        # None = system default input
    "sensitivity": 1.0,        # threshold multiplier, 0.5 .. 2.0
    "style": "cartoon",        # "cartoon" (drawn face) or "photo" (cut-out of your own head)
    "voice_expressions": True,
    "photo": "bike",           # which photo profile to use when style == "photo"
}


def config_exists():
    return os.path.exists(SETTINGS_PATH)


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
