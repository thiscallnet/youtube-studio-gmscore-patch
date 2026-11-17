[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $SourceUrl,

    [string] $AndroidSdk = $env:ANDROID_HOME,

    [string] $BundleVersion = '1.0.0'
)

$ErrorActionPreference = 'Stop'
$sourceCommit = '261981469c969bd6cc6b55b93c70166efba79e13'
$upstreamUrl = 'https://github.com/MrHuaweiFan/GmsCore-Patches.git'
$root = Split-Path -Parent $PSScriptRoot
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('studio-gmscore-build-' + [guid]::NewGuid().ToString('N'))
$sourceDir = Join-Path $tempRoot 'upstream'
$authSet = $false
$locationPushed = $false

function Invoke-Checked([string] $Name, [scriptblock] $Action) {
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

try {
    if ([string]::IsNullOrWhiteSpace($AndroidSdk)) {
        $AndroidSdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
    }
    if (-not (Test-Path (Join-Path $AndroidSdk 'platforms')) -or
        -not (Test-Path (Join-Path $AndroidSdk 'build-tools'))) {
        throw 'Set AndroidSdk to an installed Android SDK directory.'
    }
    if ($SourceUrl -notmatch '^https://github\.com/[^/]+/[^/]+/?$') {
        throw 'SourceUrl must be a GitHub repository URL with owner and name.'
    }
    if ($BundleVersion -notmatch '^\d+\.\d+\.\d+$') {
        throw 'BundleVersion must use MAJOR.MINOR.PATCH format.'
    }

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw 'GitHub CLI is required for the upstream Gradle dependency.'
    }
    $actor = (& gh api user --jq .login 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($actor)) {
        throw 'Authenticate GitHub CLI with gh auth login before building.'
    }
    $token = (& gh auth token 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($token)) {
        throw 'GitHub CLI did not provide a build token.'
    }
    $env:GITHUB_ACTOR = $actor
    $env:GITHUB_TOKEN = $token
    $authSet = $true

    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    Invoke-Checked 'Clone' { git clone --quiet --no-checkout $upstreamUrl $sourceDir }
    Invoke-Checked 'Checkout' { git -C $sourceDir checkout --quiet --detach $sourceCommit }
    Invoke-Checked 'Patch check' { git -C $sourceDir apply --check (Join-Path $root 'source.patch') }
    Invoke-Checked 'Apply source patch' { git -C $sourceDir apply (Join-Path $root 'source.patch') }

    Push-Location $sourceDir
    $locationPushed = $true
    if ($env:OS -eq 'Windows_NT') {
        $gradle = Join-Path $sourceDir 'gradlew.bat'
    } else {
        $gradle = Join-Path $sourceDir 'gradlew'
        Invoke-Checked 'Set Gradle wrapper permissions' { chmod +x $gradle }
    }
    Invoke-Checked 'Build upstream patches' {
        & $gradle :patches:generatePatchesList :patches:buildAndroid --no-daemon
    }
    Pop-Location
    $locationPushed = $false

    $bundlePath = Join-Path $sourceDir 'patches\build\libs\patches-1.2.3.mpp'
    if (-not (Test-Path $bundlePath)) {
        throw 'Gradle did not produce the expected source bundle.'
    }
    $outputDir = Join-Path $root 'dist'
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    $outputPath = Join-Path $outputDir ('youtube-studio-gmscore-patch-' + $BundleVersion + '.mpp')
    $filterArgs = @(
        '--input', $bundlePath,
        '--output', $outputPath,
        '--android-sdk', $AndroidSdk,
        '--source-url', $SourceUrl.TrimEnd('/'),
        '--version', $BundleVersion
    )
    Invoke-Checked 'Filter Studio bundle' {
        & python (Join-Path $PSScriptRoot 'filter_bundle.py') @filterArgs
    }
    Write-Output "Bundle written to $outputPath"
} finally {
    if ($locationPushed) {
        Pop-Location
    }
    if ($authSet) {
        Remove-Item Env:\GITHUB_ACTOR -ErrorAction SilentlyContinue
        Remove-Item Env:\GITHUB_TOKEN -ErrorAction SilentlyContinue
    }
    if (Test-Path $tempRoot) {
        $tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        $tempPrefix = $tempBase.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
        $resolvedTempRoot = [System.IO.Path]::GetFullPath($tempRoot)
        $tempLeaf = [System.IO.Path]::GetFileName($resolvedTempRoot)
        if (-not $resolvedTempRoot.StartsWith($tempPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
            $tempLeaf -notmatch '^studio-gmscore-build-[0-9a-f]{32}$') {
            throw 'Refusing to remove a path outside the generated temporary build directory.'
        }
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
    }
}