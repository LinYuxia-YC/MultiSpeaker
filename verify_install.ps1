# Verify the per-user installation of MultiSpeaker.
$ErrorActionPreference = 'Continue'
$install = Join-Path $env:LOCALAPPDATA 'Programs\MultiSpeaker'
$exe = Join-Path $install 'MultiSpeaker.exe'
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\MultiSpeaker'
$desktop = [Environment]::GetFolderPath('Desktop')
$report = [ordered]@{}

$report['install_dir'] = $install
$report['install_exists'] = Test-Path $install
$report['exe_exists'] = Test-Path $exe
$report['exe_version'] = if (Test-Path $exe) { (Get-Item $exe).VersionInfo.FileVersion } else { '' }
$report['exe_size_mb'] = if (Test-Path $exe) { [math]::Round((Get-ChildItem $install -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1) } else { 0 }
$report['startmenu_lnk'] = (Test-Path (Join-Path $startMenu 'MultiSpeaker.lnk'))
$report['desktop_lnk'] = (Test-Path (Join-Path $desktop 'MultiSpeaker.lnk'))
$report['uninstall_exe'] = (Test-Path (Join-Path $install 'unins000.exe'))
$report['guide'] = (Test-Path (Join-Path $install '使用说明.txt'))

$keys = @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$found = $null
foreach ($k in $keys) {
    $found = Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like 'MultiSpeaker*' } | Select-Object -First 1
    if ($found) { break }
}
$report['uninstall_entry'] = if ($found) { "$($found.DisplayName) | $($found.DisplayVersion) | $($found.InstallLocation)" } else { 'NOT FOUND' }

if (Test-Path $desktop) {
    $lnk = Join-Path $desktop 'MultiSpeaker.lnk'
    if (Test-Path $lnk) {
        $sh = New-Object -ComObject WScript.Shell
        $s = $sh.CreateShortcut($lnk)
        $report['desktop_target'] = $s.TargetPath
    }
}

$report.GetEnumerator() | ForEach-Object { "{0,-18} : {1}" -f $_.Key, $_.Value }
