param(
    [string]$Python = 'python',
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$frontend = Join-Path $projectRoot 'frontend'
$buildEnv = Join-Path $projectRoot '.build-venv'
$buildPython = Join-Path $buildEnv 'Scripts\python.exe'
$frontendDist = Join-Path $frontend 'dist'

if (-not $SkipFrontendBuild) {
    Push-Location $frontend
    try { & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
    finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendDist 'index.html'))) {
    throw 'Built frontend is missing.'
}
if (-not (Test-Path -LiteralPath $buildPython)) {
    & $Python -m venv $buildEnv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create build environment.' }
}
& $buildPython -m pip install -r (Join-Path $projectRoot 'backend\requirements.txt') 'pyinstaller>=6.19,<7'
if ($LASTEXITCODE -ne 0) { throw 'Could not install build dependencies.' }

$distTarget = Join-Path $projectRoot 'release'
$workTarget = Join-Path $projectRoot 'build\pyinstaller'
$specTarget = Join-Path $projectRoot 'build'
New-Item -ItemType Directory -Force -Path $distTarget,$workTarget,$specTarget | Out-Null
& $buildPython -m PyInstaller --noconfirm --clean --onedir --console `
    --name StoryForge --paths (Join-Path $projectRoot 'backend') `
    --add-data "$frontendDist;frontend/dist" --collect-submodules keyring `
    --distpath $distTarget --workpath $workTarget --specpath $specTarget `
    (Join-Path $projectRoot 'backend\desktop_launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
Write-Host "Build: $(Join-Path $distTarget 'StoryForge\StoryForge.exe')"
Write-Host 'FFmpeg/FFprobe are not bundled. Check license terms before distributing binaries.'
