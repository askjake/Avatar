"""virtual_cam.py - pushes frames to the OBS Virtual Camera via pyvirtualcam."""
import threading
from avatar_renderer import W, H

FPS = 20


class VirtualCam(threading.Thread):
    def __init__(self, frame_fn, on_error=None):
        super().__init__(daemon=True)
        self.frame_fn = frame_fn      # callable returning a 640x480 RGB uint8 array
        self.on_error = on_error
        self.running = threading.Event()
        self.running.set()
        self.error = None

    def run(self):
        try:
            import pyvirtualcam
            with pyvirtualcam.Camera(width=W, height=H, fps=FPS, fmt=pyvirtualcam.PixelFormat.RGB) as cam:
                print("Virtual camera running as:", cam.device)
                while self.running.is_set():
                    cam.send(self.frame_fn())
                    cam.sleep_until_next_frame()
        except Exception as e:
            self.error = ("Could not open the virtual camera. Is OBS Studio installed "
                          "(Tools > Virtual Camera driver)? Details: %s" % e)
            print(self.error)
            if self.on_error:
                self.on_error(self.error)

    def stop(self):
        self.running.clear()
