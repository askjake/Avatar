"""settings_ui.py - small tkinter settings window."""
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox
from pathlib import Path
import uuid
from landmarks import detect, open_photo
from config import SKIN_PRESETS, HAIR_PRESETS


def list_mics():
    """[(label, device_index)] for all input devices."""
    try:
        import sounddevice as sd
        return [("%d: %s" % (i, d["name"]), i) for i, d in enumerate(sd.query_devices())
                if d["max_input_channels"] > 0]
    except Exception:
        return []


def show_settings(cfg, start_label="Start AvatarCam"):
    """Blocks until closed. Returns the new cfg dict, or None if the window was closed/cancelled."""
    root = tk.Tk()
    root.title("AvatarCam Settings")
    root.resizable(False, False)
    result = {}
    state = {"skin": cfg["skin"], "hair": cfg["hair"], "background": cfg["background"]}
    pad = {"padx": 8, "pady": 5}

    ttk.Label(root, text="Name badge:").grid(row=0, column=0, sticky="w", **pad)
    name_var = tk.StringVar(value=cfg["name"])
    ttk.Entry(root, textvariable=name_var, width=28).grid(row=0, column=1, columnspan=2, sticky="w", **pad)

    # ---- face style: cartoon (drawn) or photo (cut-out of your own head) ----
    try:
        import photo_avatar as pa
        profiles = pa.load_profiles()
    except Exception:
        pa, profiles = None, {}
    ttk.Label(root, text="Avatar style:").grid(row=1, column=0, sticky="w", **pad)
    style_var = tk.StringVar(value="Photo portrait" if cfg.get("style") == "photo" else "Cartoon")
    style_frame = ttk.Frame(root); style_frame.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
    ttk.Combobox(style_frame, textvariable=style_var, values=["Cartoon", "Photo portrait"],
                 state="readonly", width=14).pack(side="left")
    pkeys = list(profiles.keys())
    plabels = [profiles[k].get("label", k) for k in pkeys]
    photo_var = tk.StringVar(value=plabels[pkeys.index(cfg.get("photo"))] if cfg.get("photo") in pkeys
                             else (plabels[0] if plabels else ""))
    photo_box = ttk.Combobox(style_frame, textvariable=photo_var, values=plabels, state="readonly", width=12)
    photo_box.pack(side="left", padx=6)

    def import_photo():
        path = filedialog.askopenfilename(parent=root, filetypes=[("Photos","*.jpg *.jpeg *.png *.webp")])
        if not path:
            return
        try:
            profile = detect(open_photo(path, True))
            key = uuid.uuid4().hex
            label = Path(path).stem
            if label in plabels:
                label += " " + key[:5]
            profile.update(file=path, label=label, oriented=True)
            current = pa.load_profiles()
            current[key] = profile
            pa.save_profiles(current)
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Import photo", str(exc), parent=root)
            return
        pkeys.append(key)
        plabels.append(label)
        photo_box.configure(values=plabels)
        photo_var.set(label)
        style_var.set("Photo portrait")
        do_face_setup()

    ttk.Button(style_frame, text="Import photo", command=import_photo).pack(side="left")
    def do_face_setup():
        if pa is None or not pkeys:
            return
        from face_setup import open_setup
        sel = pkeys[plabels.index(photo_var.get())] if photo_var.get() in plabels else pkeys[0]
        open_setup(root, sel)
    ttk.Button(style_frame, text="Set up face...", command=do_face_setup).pack(side="left")

    def swatch_row(row, label, key, presets):
        ttk.Label(root, text=label).grid(row=row, column=0, sticky="w", **pad)
        frame = tk.Frame(root); frame.grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        buttons = {}
        def pick(c):
            state[key] = c
            for col, b in buttons.items():
                b.config(relief="sunken" if col == c else "raised", bd=3 if col == c else 1)
        for c in presets:
            b = tk.Button(frame, bg=c, width=3, command=lambda c=c: pick(c))
            b.pack(side="left", padx=2); buttons[c] = b
        pick(state[key])

    swatch_row(2, "Skin tone (cartoon):", "skin", SKIN_PRESETS)
    swatch_row(3, "Hair color (cartoon):", "hair", HAIR_PRESETS)

    ttk.Label(root, text="Background:").grid(row=4, column=0, sticky="w", **pad)
    bg_btn = tk.Button(root, bg=state["background"], width=8)
    def pick_bg():
        c = colorchooser.askcolor(color=state["background"], parent=root)[1]
        if c:
            state["background"] = c; bg_btn.config(bg=c)
    bg_btn.config(command=pick_bg); bg_btn.grid(row=4, column=1, sticky="w", **pad)

    ttk.Label(root, text="Microphone:").grid(row=5, column=0, sticky="w", **pad)
    mics = [("System default", None)] + list_mics()
    labels = [m[0] for m in mics]
    cur = next((i for i, m in enumerate(mics) if m[1] == cfg["mic_device"]), 0)
    mic_var = tk.StringVar(value=labels[cur])
    ttk.Combobox(root, textvariable=mic_var, values=labels, state="readonly", width=40).grid(
        row=5, column=1, columnspan=2, sticky="w", **pad)

    ttk.Label(root, text="Threshold scale:").grid(row=6, column=0, sticky="w", **pad)
    sens = tk.DoubleVar(value=cfg["sensitivity"])
    tk.Scale(root, variable=sens, from_=0.5, to=2.0, resolution=0.05, orient="horizontal", length=220).grid(
        row=6, column=1, sticky="w", **pad)
    ttk.Label(root, text="0.5 = very sensitive\n2.0 = needs louder voice", foreground="gray").grid(row=6, column=2, **pad)

    expression_var = tk.BooleanVar(value=cfg.get("voice_expressions", True))
    ttk.Checkbutton(root, text="Voice-driven expressions (photo portrait)", variable=expression_var).grid(
        row=7, column=0, columnspan=3, sticky="w", **pad)

    ttk.Label(root, text="Portrait expression:").grid(row=8, column=0, sticky="w", **pad)
    pose = tk.StringVar(value=cfg.get("portrait_pose", "Voice"))
    ttk.Combobox(root, textvariable=pose, state="readonly",
                 values=("Voice","Neutral","Happiness","Sadness","Anger","Fear","Surprise","Disgust")).grid(
                     row=8,column=1,sticky="w",**pad)

    def on_start():
        sel = labels.index(mic_var.get()) if mic_var.get() in labels else 0
        photo_key = pkeys[plabels.index(photo_var.get())] if photo_var.get() in plabels else cfg.get("photo", "bike")
        result.update(cfg)
        result.update(portrait_pose=pose.get(), voice_expressions=expression_var.get(), name=name_var.get().strip(), skin=state["skin"], hair=state["hair"],
                      background=state["background"], mic_device=mics[sel][1], sensitivity=float(sens.get()),
                      style="photo" if style_var.get().startswith("Photo") else "cartoon", photo=photo_key)
        root.destroy()

    ttk.Button(root, text=start_label, command=on_start).grid(row=9, column=0, columnspan=3, pady=12)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return dict(result) if result else None
