# Troubleshooting

## 1. Camera won't open / "OBS Virtual Camera" not in Meet
Symptoms: console says `OBS Virtual Camera device not found`, tray shows "Camera error", or Meet's list has no OBS Virtual Camera.

1. Is OBS installed? `winget list OBSProject.OBSStudio`. If not, run the user-scope install from the README.
2. Is the driver registered for your user? Run `powershell -ExecutionPolicy Bypass -File register_camera_user.ps1`. Expect `OK`.
   (`regsvr32 /n /i:user` fails with exit code 5 without admin. That is why the script exists.)
3. **Fully quit and reopen Chrome.** Chrome only scans cameras at startup.
4. Make sure only one AvatarCam is running (Task Manager > python.exe). A second copy cannot take the camera.
5. If OBS itself has its Virtual Camera started, stop it.
6. Test directly: `python -c "import pyvirtualcam; c=pyvirtualcam.Camera(1280,720,20); print('OK'); c.close()"`
7. In Meet make sure your camera is turned **on** (a crossed-out camera icon means off, not a driver fault).

## 2. Mouth doesn't move
1. Tray menu > **Settings...** and pick your real microphone (for example your headset) instead of "System default", then Save.
2. Windows Settings > Privacy > Microphone: allow desktop apps, and make sure the mic isn't muted.
3. Lower the **Threshold scale** slider toward 0.5 (more sensitive).
4. Tray > **Recalibrate Mic**, staying silent for 1 second. If you talked during startup, the noise floor may be too high.
5. Still flat? Try the other mic in the list. A baseline of exactly 0.0 in the console usually means a muted or wrong device.

## 3. High CPU
Expected: well under 15% of total CPU (about 4% measured).
1. Close duplicate AvatarCam copies.
2. Lower `FPS` in `virtual_cam.py` (20 -> 15 or 12).
3. Shrink the output: in `avatar_renderer.py` set a smaller `W, H` (keep it at least 640x480, since the scene is centred on it).
4. Close other apps that are reading the OBS Virtual Camera.
