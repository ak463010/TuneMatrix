param(
    [string]$BuildDir = "build/analysis_helper_nmake",
    [switch]$EnableEssentia,
    [string]$EssentiaRoot = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$buildPath = Join-Path $repoRoot $BuildDir

$vsDevCmd = "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat"
$cmake = "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"

if (-not (Test-Path $vsDevCmd)) {
    throw "VsDevCmd.bat was not found at '$vsDevCmd'."
}

if (-not (Test-Path $cmake)) {
    throw "Bundled CMake was not found at '$cmake'."
}

if (Test-Path $buildPath) {
    Remove-Item $buildPath -Recurse -Force
}

$sourceDir = Join-Path $repoRoot "native/analysis_helper"
$configureArgs = @(
    "-S", "`"$sourceDir`"",
    "-B", "`"$buildPath`"",
    "-G", "`"NMake Makefiles`"",
    "-DCMAKE_CXX_SCAN_FOR_MODULES=OFF"
)

if ($EnableEssentia) {
    $configureArgs += "-DTM_ANALYSIS_HELPER_ENABLE_ESSENTIA=ON"
    if (-not [string]::IsNullOrWhiteSpace($EssentiaRoot)) {
        $configureArgs += "-DTM_ANALYSIS_HELPER_ESSENTIA_ROOT=`"$EssentiaRoot`""
    }
}

$configureText = [string]::Join(" ", $configureArgs)
$cmdline = 'call "{0}" -arch=x64 -host_arch=x64 >nul && "{1}" {2} && "{1}" --build "{3}"' -f $vsDevCmd, $cmake, $configureText, $buildPath

& $env:ComSpec /d /c $cmdline
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
