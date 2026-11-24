"""settings_ui.py - small tkinter settings window."""
import tkinter as tk
from tkinter import ttk, colorchooser
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

    swatch_row(1, "Skin tone:", "skin", SKIN_PRESETS)
    swatch_row(2, "Hair color:", "hair", HAIR_PRESETS)

    ttk.Label(root, text="Background:").grid(row=3, column=0, sticky="w", **pad)
    bg_btn = tk.Button(root, bg=state["background"], width=8)
    def pick_bg():
        c = colorchooser.askcolor(color=state["background"], parent=root)[1]
        if c:
            state["background"] = c; bg_btn.config(bg=c)
    bg_btn.config(command=pick_bg); bg_btn.grid(row=3, column=1, sticky="w", **pad)

    ttk.Label(root, text="Microphone:").grid(row=4, column=0, sticky="w", **pad)
    mics = [("System default", None)] + list_mics()
    labels = [m[0] for m in mics]
    cur = next((i for i, m in enumerate(mics) if m[1] == cfg["mic_device"]), 0)
    mic_var = tk.StringVar(value=labels[cur])
    ttk.Combobox(root, textvariable=mic_var, values=labels, state="readonly", width=40).grid(
        row=4, column=1, columnspan=2, sticky="w", **pad)

    ttk.Label(root, text="Threshold scale:").grid(row=5, column=0, sticky="w", **pad)
    sens = tk.DoubleVar(value=cfg["sensitivity"])
    tk.Scale(root, variable=sens, from_=0.5, to=2.0, resolution=0.05, orient="horizontal", length=220).grid(
        row=5, column=1, sticky="w", **pad)
    ttk.Label(root, text="0.5 = very sensitive\n2.0 = needs louder voice", foreground="gray").grid(row=5, column=2, **pad)

    def on_start():
        sel = labels.index(mic_var.get()) if mic_var.get() in labels else 0
        result.update(cfg)
        result.update(name=name_var.get().strip(), skin=state["skin"], hair=state["hair"],
                      background=state["background"], mic_device=mics[sel][1], sensitivity=float(sens.get()))
        root.destroy()

    ttk.Button(root, text=start_label, command=on_start).grid(row=6, column=0, columnspan=3, pady=12)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return dict(result) if result else None
