"""main.py - AvatarCam entry point: settings window -> audio + render threads -> tray."""
import threading
import config
from audio_monitor import AudioMonitor
from avatar_renderer import AvatarRenderer
from virtual_cam import VirtualCam
from settings_ui import show_settings
from tray import build_tray


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.audio = AudioMonitor(cfg["mic_device"], cfg["sensitivity"])
        self.renderer = AvatarRenderer(cfg)
        self.render_lock = threading.Lock()
        self.cam = None
        self.status = "Starting"
        self.icon = None
        self.settings_open = False

    def frame(self):
        level, _rms, listening = self.audio.get_state()
        with self.render_lock:
            return self.renderer.render(level, listening)

    def start(self):
        self.audio.start()
        if self.audio.error:
            print("Microphone error:", self.audio.error)
            self.status = "Mic error"
        else:
            self.audio.calibrate(1.0)   # 1 s of silence -> noise floor
            self.status = "Running"
        self.cam = VirtualCam(self.frame, on_error=lambda e: setattr(self, "status", "Camera error"))
        self.cam.start()

    def open_settings(self):
        if self.settings_open:
            return
        self.settings_open = True
        old = self.status
        self.status = "Paused"
        try:
            new = show_settings(self.cfg, "Save")
            if new:
                self.cfg = new
                config.save_config(new)
                with self.render_lock:
                    self.renderer.set_config(new)
                self.audio.sensitivity = new["sensitivity"]
                if new["mic_device"] != self.audio.device:
                    self.audio.device = new["mic_device"]
                    self.audio.start()
                    self.audio.calibrate(1.0)
        finally:
            self.settings_open = False
            self.status = "Mic error" if self.audio.error else (old if old != "Paused" else "Running")

    def recalibrate(self):
        threading.Thread(target=self.audio.calibrate, args=(1.0,), daemon=True).start()

    def quit(self, icon):
        if self.cam:
            self.cam.stop()
        self.audio.stop()
        icon.stop()

    def status_text(self):
        return {"Running": "\u2705 Running", "Paused": "\u23f8 Paused"}.get(self.status, "\u26a0 " + self.status)


def main():
    first_run = not config.config_exists()
    cfg = config.load_config()
    if first_run:
        new = show_settings(cfg)
        if not new:
            return                      # window closed without starting
        cfg = new
        config.save_config(cfg)

    app = App(cfg)
    app.start()
    app.icon = build_tray(app.status_text,
                          lambda: threading.Thread(target=app.open_settings, daemon=True).start(),
                          app.recalibrate, app.quit, cfg["skin"], cfg["hair"])
    app.icon.run()                      # blocks until Quit


if __name__ == "__main__":
    main()
