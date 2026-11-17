# Rebuild the bundle

The release bundle can be rebuilt from its pinned source.

Requirements: Git, GitHub CLI authenticated for GitHub Packages, Java, Python 3, Windows PowerShell 5.1 or PowerShell 7, and an Android SDK with build-tools and an Android platform installed.

From this repository, run:

    powershell.exe -ExecutionPolicy Bypass -File .\tools\build-bundle.ps1 -AndroidSdk "$env:ANDROID_HOME" -SourceUrl https://github.com/thiscallnet/youtube-studio-gmscore-patch

The script clones the pinned public source, applies source.patch, builds the upstream patches bundle, and writes dist/youtube-studio-gmscore-patch-1.0.0.mpp. GitHub CLI credentials are read into temporary build environment variables and removed on exit.