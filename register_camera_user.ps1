<#
 register_camera_user.ps1 - register the OBS Virtual Camera DirectShow filter WITHOUT admin rights.
 Usage:  powershell -ExecutionPolicy Bypass -File register_camera_user.ps1 [-Dll <path>] [-Unregister]
 Why: regsvr32 and OBS's own installer write to HKLM (needs admin). This redirects HKEY_CLASSES_ROOT
 to HKCU\Software\Classes for this process only, then calls the DLL's own DllRegisterServer.
 After registering, FULLY restart Chrome (it only scans cameras at startup).
#>
param([string]$Dll = "", [switch]$Unregister)
if (-not $Dll) {
  $roots = @("$env:LOCALAPPDATA\Microsoft\WinGet\Packages", "$env:LOCALAPPDATA\Programs", "$env:ProgramFiles\obs-studio")
  foreach ($r in $roots) { if (Test-Path $r) {
    $f = Get-ChildItem $r -Recurse -Filter obs-virtualcam-module64.dll -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($f) { $Dll = $f.FullName; break } } }
}
if (-not $Dll -or -not (Test-Path $Dll)) { Write-Host "obs-virtualcam-module64.dll not found. Install OBS first (see README)."; exit 1 }
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class UserReg {
  [DllImport("advapi32.dll")] public static extern int RegOverridePredefKey(IntPtr hKey, IntPtr hNew);
  [DllImport("advapi32.dll")] public static extern int RegCreateKeyEx(IntPtr h, string sub, int res, string cls, int opt, int sam, IntPtr sa, out IntPtr res2, out int disp);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern IntPtr LoadLibrary(string p);
  [DllImport("kernel32.dll", CharSet=CharSet.Ansi)] public static extern IntPtr GetProcAddress(IntPtr m, string n);
  [UnmanagedFunctionPointer(CallingConvention.StdCall)] public delegate int Fn();
  public static int Run(string dll, string export) {
    IntPtr hcu = new IntPtr(unchecked((int)0x80000001)), hcr = new IntPtr(unchecked((int)0x80000000)), k; int d;
    int r = RegCreateKeyEx(hcu, "Software\\Classes", 0, null, 0, 0xF003F, IntPtr.Zero, out k, out d);
    if (r != 0) return -1000 - r;
    r = RegOverridePredefKey(hcr, k); if (r != 0) return -2000 - r;
    IntPtr m = LoadLibrary(dll); if (m == IntPtr.Zero) return -3000 - Marshal.GetLastWin32Error();
    IntPtr p = GetProcAddress(m, export); if (p == IntPtr.Zero) return -4000;
    return ((Fn)Marshal.GetDelegateForFunctionPointer(p, typeof(Fn)))();
  }
}
"@
$export = if ($Unregister) { "DllUnregisterServer" } else { "DllRegisterServer" }
$rc = [UserReg]::Run($Dll, $export)
if ($rc -eq 0) { Write-Host "OK: $export succeeded for $Dll" } else { Write-Host ("FAILED: code 0x{0:X}" -f $rc); exit 1 }
