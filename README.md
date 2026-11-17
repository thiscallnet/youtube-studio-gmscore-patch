# YouTube Studio GmsCore Patch

A compact patch source for use with Morphe Manager.

## Add it in Morphe Manager

1. Open Sources, tap +, and add this repository:
   https://github.com/thiscallnet/youtube-studio-gmscore-patch
2. Open YouTube Studio and patch version 26.46.000 (version code 126460007) with GmsCore support.
3. Install a compatible [Morphe MicroG-RE build](https://github.com/MorpheApp/MicroG-RE/releases) separately.

This bundle includes GmsCore support and its shared package-name support. The patched app uses package name app.morphe.android.youtube.creator and can be installed alongside the original Studio app. This source does not distribute YouTube Studio or MicroG APKs.

## Verification

Morphe Manager 2.6.0 applied the Studio patch (1 selected patch) to YouTube Studio 26.46.000 on an Android 14 (API 34) x86_64 AVD. The Studio APK itself was ARM64, so it was not launched on that AVD. Account sign-in through MicroG-RE has not been verified.

## Source and license

The patch is based on [MrHuaweiFan/GmsCore-Patches v1.2.3](https://github.com/MrHuaweiFan/GmsCore-Patches/tree/261981469c969bd6cc6b55b93c70166efba79e13) and [Morphe patch APIs](https://github.com/MorpheApp/morphe-patches). See [SOURCE.md](SOURCE.md) for provenance. GPL-3.0 and the included [NOTICE](NOTICE) apply.