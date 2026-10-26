# Build MultiSpeaker: onedir (installer payload) + onefile portable, then verify.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'

$common = @(
    '--noconfirm', '--clean', '--windowed', '--icon', 'app\resources\app.ico',
    '--add-data', 'app\resources;app\resources',
    '--collect-data', '_sounddevice_data',
    '--collect-binaries', 'av', '--collect-binaries', 'soxr',
    '--paths', '.',
    '--exclude-module', 'tkinter', '--exclude-module', 'matplotlib',
    '--exclude-module', 'scipy', '--exclude-module', 'pandas',
    '--exclude-module', 'PySide6.QtWebEngineCore', '--exclude-module', 'PySide6.QtWebEngineWidgets',
    '--exclude-module', 'PySide6.QtQml', '--exclude-module', 'PySide6.QtQuick',
    '--exclude-module', 'PySide6.QtMultimedia', '--exclude-module', 'PySide6.QtPdf',
    '--exclude-module', 'PySide6.QtSql', '--exclude-module', 'PySide6.QtTest',
    '--exclude-module', 'PySide6.QtBluetooth', '--exclude-module', 'PySide6.QtCharts',
    '--exclude-module', 'PySide6.QtDesigner', '--exclude-module', 'PySide6.QtOpenGL',
    '--version-file', 'build\version_info.txt'
)

Write-Host '=== [1/4] onedir build ==='
python -m PyInstaller @common --name MultiSpeaker main.py 2>&1 | Tee-Object build\pyi-onedir.log | Select-Object -Last 4
if (-not (Test-Path 'dist\MultiSpeaker\MultiSpeaker.exe')) { throw 'onedir build failed' }

Write-Host '=== [2/4] prune unused Qt payload ==='
$internal = 'dist\MultiSpeaker\_internal'
Remove-Item "$internal\PySide6\translations" -Recurse -Force -ErrorAction SilentlyContinue
foreach ($f in 'opengl32sw.dll', 'Qt6Quick.dll', 'Qt6Qml.dll', 'Qt6QmlModels.dll',
               'Qt6QmlMeta.dll', 'Qt6QmlWorkerScript.dll', 'Qt6Pdf.dll', 'Qt6VirtualKeyboard.dll') {
    Remove-Item "$internal\PySide6\$f" -Force -ErrorAction SilentlyContinue
}
$mb = [math]::Round((Get-ChildItem 'dist\MultiSpeaker' -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "    onedir size: $mb MB"

Write-Host '=== [3/4] verify packaged app ==='
Remove-Item build\exe-selftest.log -ErrorAction SilentlyContinue
$p = Start-Process 'dist\MultiSpeaker\MultiSpeaker.exe' -ArgumentList '--selftest', '--log', 'build\exe-selftest.log' -Wait -PassThru
Write-Host "    selftest exit: $($p.ExitCode)"
if (Test-Path build\exe-selftest.log) { Get-Content build\exe-selftest.log | Select-Object -Last 6 }
$p = Start-Process 'dist\MultiSpeaker\MultiSpeaker.exe' -ArgumentList '--screenshot', 'build\exe-shot.png' -Wait -PassThru
Write-Host "    screenshot exit: $($p.ExitCode); png exists: $(Test-Path build\exe-shot.png)"
if ($p.ExitCode -ne 0) { throw 'packaged app failed to render' }

Write-Host '=== [4/4] onefile portable build ==='
python -m PyInstaller @common --onefile --name MultiSpeaker-Portable main.py 2>&1 | Tee-Object build\pyi-onefile.log | Select-Object -Last 4
$exe = 'dist\MultiSpeaker-Portable.exe'
$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "    portable exe: $mb MB"
Remove-Item build\portable-selftest.log -ErrorAction SilentlyContinue
$p = Start-Process $exe -ArgumentList '--selftest', '--log', 'build\portable-selftest.log' -Wait -PassThru
Write-Host "    portable selftest exit: $($p.ExitCode)"
if (Test-Path build\portable-selftest.log) { Get-Content build\portable-selftest.log | Select-Object -Last 4 }
Write-Host 'BUILD DONE'
