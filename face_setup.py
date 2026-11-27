"""face_setup.py - tiny tkinter window to place the face landmarks on a photo (a few clicks).

Opened from Settings > "Set up face...". Defaults are already filled in, so you only need this if the
jaw split / eyes / head outline look off. Landmarks are saved to photos/profiles.json.
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk
import os
import photo_avatar as pa

MAX_W, MAX_H = 520, 680

STEPS = [
    ("left_eye", "Click the CENTRE of the eye on the LEFT of the photo"),
    ("right_eye", "Click the CENTRE of the eye on the RIGHT of the photo"),
    ("mouth", "Click the middle of your mouth where the jaw should split (just under the mustache / top teeth)"),
    ("mouth_r", "Click the RIGHT corner of your mouth (sets mouth width)"),
    ("chin", "Click the very bottom of your chin"),
    ("top", "Click the very top of your head (or hat)"),
    ("left", "Click the far LEFT edge of your head (ears / hat)"),
    ("right", "Click the far RIGHT edge of your head (ears / hat)"),
]


def open_setup(parent, key="bike"):
    """Modal Toplevel. Returns True if the user saved."""
    profiles = pa.load_profiles()
    saved = {"ok": False}
    win = tk.Toplevel(parent)
    win.title("AvatarCam - set up face")
    win.resizable(False, False)

    top = ttk.Frame(win); top.pack(fill="x", padx=8, pady=6)
    ttk.Label(top, text="Photo:").pack(side="left")
    keys = list(profiles.keys())
    labels = [profiles[k].get("label", k) for k in keys]
    var = tk.StringVar(value=labels[keys.index(key)] if key in keys else labels[0])
    combo = ttk.Combobox(top, textvariable=var, values=labels, state="readonly", width=16)
    combo.pack(side="left", padx=6)
    prompt = tk.StringVar(value="Defaults shown. Click 'Redo clicks' to re-place the points, or Save.")
    ttk.Label(win, textvariable=prompt, wraplength=520, foreground="#224").pack(fill="x", padx=8)

    canvas = tk.Canvas(win, width=MAX_W, height=MAX_H, bg="#222", highlightthickness=0)
    canvas.pack(padx=8, pady=6)
    state = {"key": keys[0], "img": None, "scale": 1.0, "tk": None, "step": None, "clicks": {}}

    def cur():
        return profiles[state["key"]]

    def draw():
        p = cur()
        im = state["img"].copy(); d = ImageDraw.Draw(im)
        d.ellipse((p["left"], p["top"], p["right"], p["chin"]), outline=(255, 255, 255), width=3)
        for k in ("left_eye", "right_eye"):
            x, y = p[k]; d.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(0, 255, 0), width=3)
        mx, my = p["mouth"]
        d.line((mx - p["mouth_hw"] * 1.4, my, mx + p["mouth_hw"] * 1.4, my), fill=(255, 0, 0), width=3)
        d.ellipse((mx - p["mouth_hw"], my - 14, mx + p["mouth_hw"], my + 14), outline=(255, 160, 0), width=2)
        s = state["scale"]
        im = im.resize((int(im.width * s), int(im.height * s)))
        state["tk"] = ImageTk.PhotoImage(im)
        canvas.delete("all"); canvas.create_image(0, 0, anchor="nw", image=state["tk"])

    def load(k):
        state["key"] = k; state["step"] = None
        path = os.path.join(pa.HERE, cur()["file"])
        im = Image.open(path).convert("RGB")
        state["img"] = im
        state["scale"] = min(MAX_W / im.width, MAX_H / im.height, 1.0)
        canvas.config(width=int(im.width * state["scale"]), height=int(im.height * state["scale"]))
        draw()

    def on_combo(_e=None):
        load(keys[labels.index(var.get())])
        prompt.set("Defaults shown. Click 'Redo clicks' to re-place the points, or Save.")

    def next_prompt():
        i = state["step"]
        prompt.set("(%d/%d) %s" % (i + 1, len(STEPS), STEPS[i][1]))

    def redo():
        state["step"] = 0; state["clicks"] = {}; next_prompt()

    def on_click(ev):
        if state["step"] is None:
            return
        s = state["scale"]; x, y = ev.x / s, ev.y / s
        name = STEPS[state["step"]][0]
        state["clicks"][name] = (x, y)
        state["step"] += 1
        if state["step"] >= len(STEPS):
            c = state["clicks"]; p = cur()
            p["left_eye"], p["right_eye"] = [c["left_eye"][0], c["left_eye"][1]], [c["right_eye"][0], c["right_eye"][1]]
            p["mouth"] = [c["mouth"][0], c["mouth"][1]]
            p["mouth_hw"] = max(15.0, abs(c["mouth_r"][0] - c["mouth"][0]))
            p["chin"], p["top"] = c["chin"][1], c["top"][1]
            p["left"], p["right"] = c["left"][0], c["right"][0]
            state["step"] = None
            prompt.set("Done. Check the white ellipse (head), green circles (eyes) and red line (jaw split). Save, or Redo.")
        else:
            next_prompt()
        draw()

    def reset():
        profiles[state["key"]].update(pa.DEFAULT_PROFILES.get(state["key"], {}))
        state["step"] = None; draw(); prompt.set("Reset to defaults.")

    def save():
        pa.save_profiles(profiles); saved["ok"] = True; win.destroy()

    canvas.bind("<Button-1>", on_click)
    combo.bind("<<ComboboxSelected>>", on_combo)
    btns = ttk.Frame(win); btns.pack(pady=8)
    ttk.Button(btns, text="Redo clicks", command=redo).pack(side="left", padx=4)
    ttk.Button(btns, text="Reset to defaults", command=reset).pack(side="left", padx=4)
    ttk.Button(btns, text="Save", command=save).pack(side="left", padx=4)
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=4)

    load(key if key in keys else keys[0])
    win.transient(parent); win.grab_set()
    parent.wait_window(win)
    return saved["ok"]
