# AvatarCam

A cartoon avatar that lip-syncs to your microphone and shows up as a webcam in Google Meet. No real webcam, no cloud, no API keys.

## Setup
1. **Install OBS Studio** (one-time, free): https://obsproject.com. This provides the virtual camera driver.
   Open OBS once and click *Start Virtual Camera* (or Tools > Virtual Camera) so the driver registers. OBS does not need to stay open afterwards.
2. Install **Python 3.11+** (tick "Add python.exe to PATH").
3. **Double-click `start_avatarcam.bat`**. It installs the dependencies on first run.
   (Optional: right-click `create_shortcut.ps1` > Run with PowerShell for a desktop shortcut with the face icon.)
4. In the settings window pick your name, skin, hair, background and microphone, then click **Start AvatarCam**.
   Stay quiet for the first second: it measures your room's noise floor.
5. In **Google Meet > Settings > Video**, choose **OBS Virtual Camera**.
6. You're live. The avatar breathes, blinks and looks around when quiet, and lip-syncs when you talk.
7. To stop: right-click the tray icon (near the clock) > **Quit**.

## Tray menu
- **Settings...** change look/mic any time (applies live)
- **Recalibrate Mic** re-measure the noise floor (be quiet for 1 second)

## Tweaking
- Colors, sizes, blink timing, bob and mouth heights: constants at the top of `avatar_renderer.py`
- RMS thresholds: `BASE_THRESHOLDS` in `audio_monitor.py`
- Mouth reacts too much or too little? Use the *Threshold scale* slider (lower = more sensitive).

## Troubleshooting
- *Camera error in tray*: OBS Virtual Camera isn't installed or is in use by OBS. Close OBS's own virtual camera.
- *Mouth never moves*: pick the right microphone in Settings, or lower the threshold scale.
- Settings are stored in `avatarcam_settings.json`; delete it to see the first-launch window again.
