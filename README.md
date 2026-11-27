# AvatarCam

A cartoon avatar that lip-syncs to your microphone and appears as a webcam in Google Meet.
Offline, no API keys, **no admin rights needed**.

## First-run setup (Windows 10/11, no admin)

**1. Check Python (3.11+).** In PowerShell: `python --version`. If missing: `winget install Python.Python.3.13 --scope user`.

**2. Install OBS Studio in user space** (it only provides the virtual camera driver):
```
winget install --id OBSProject.OBSStudio --scope user --silent --accept-package-agreements --accept-source-agreements
```

**3. Register the camera driver for your user (no admin).** The normal OBS installer and `regsvr32` need admin, so use the included script:
```
powershell -ExecutionPolicy Bypass -File register_camera_user.ps1
```
It should print `OK: DllRegisterServer succeeded`. You only do this once. (Undo with `-Unregister`.)

**4. Fully restart Chrome** (close all windows and check the tray). Chrome only scans cameras when it starts.

**5. Launch.** Double-click `start_avatarcam.bat` (installs dependencies on first run), or run `python main.py`.
Do not press Ctrl+C to stop it; use the tray's Quit. Run only one copy at a time.
Optional: right-click `create_shortcut.ps1` > Run with PowerShell for a Desktop shortcut.

**6. Settings window (first launch).** Enter your name, pick colors, and **choose your microphone explicitly**
(not "System default" unless that is your real mic), then click **Start AvatarCam**.
Stay quiet for the first second while it calibrates.

**7. Google Meet.** Join or start a meeting, turn your camera **on**, then open the camera dropdown
(or Settings > Video) and choose **OBS Virtual Camera**.

**8. Stop.** Right-click the tray icon (check the `^` overflow near the clock) > **Quit**.

## Tray menu
- **Settings...** change look or mic at any time (applies live)
- **Recalibrate Mic** re-measure room noise (be quiet for 1 second)
- **Quit**

## Tweaking
- Colors, sizes, blink timing, bob and mouth heights: constants at the top of `avatar_renderer.py`
- RMS thresholds: `BASE_THRESHOLDS` in `audio_monitor.py`
- Frame rate: `FPS` in `virtual_cam.py`
- Output is 960x540 (16:9) so Meet doesn't crop the head.

Having trouble? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Animated photo portrait
Use a photo of your own head instead of the cartoon face.
1. Put head photos in the `photos/` folder (they are git-ignored and never leave your machine). Two defaults are wired up: `head_bike.jpg` and `head_beanie.jpg`.
2. Tray icon > **Settings...** > **Avatar style: Photo portrait**, pick a photo, **Save**.
3. If the lip seam, eyes or head outline look off: Settings > **Set up face...** and click the 8 prompted points (about 30 seconds).
- Place the mouth centre at the lip seam, beneath any visible upper teeth. The lower lip and nearby skin move with calibrated microphone loudness. Blinks use the original eyelid texture.
- Motion is generated locally from one still image. It follows loudness and does not infer phonemes.
- If the photo can't be loaded, AvatarCam falls back to the cartoon face.
