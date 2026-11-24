# Right-click > Run with PowerShell: puts an "AvatarCam" shortcut (with face icon) on your Desktop.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut([Environment]::GetFolderPath("Desktop") + "\AvatarCam.lnk")
$lnk.TargetPath = "$here\start_avatarcam.bat"
$lnk.WorkingDirectory = $here
$lnk.IconLocation = "$here\avatarcam.ico"
$lnk.Save()
Write-Host "Shortcut created on Desktop."
