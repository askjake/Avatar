"""tray.py - pystray tray icon + menu."""
import pystray
from avatar_renderer import make_icon


def build_tray(get_status, on_settings, on_recalibrate, on_quit, skin, hair):
    menu = pystray.Menu(
        pystray.MenuItem(lambda item: get_status(), None, enabled=False),   # status line, not clickable
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings...", lambda icon, item: on_settings()),
        pystray.MenuItem("Recalibrate Mic", lambda icon, item: on_recalibrate()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda icon, item: on_quit(icon)),
    )
    return pystray.Icon("AvatarCam", make_icon(64, skin, hair), "AvatarCam", menu)
