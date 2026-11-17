import argparse
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import zipfile


CLASS_PREFIXES = (
    "app/morphe/patches/all/misc/packagename/",
    "app/morphe/patches/shared/compat/AppCompatibilities.class",
    "app/morphe/patches/shared/misc/extension/",
    "app/morphe/patches/shared/misc/gms/",
    "app/morphe/patches/shared/misc/mapping/",
    "app/morphe/patches/shared/misc/settings/preference/",
    "app/morphe/patches/youtubestudio/",
    "app/morphe/util/",
    "util/",
)


def parse_manifest(data):
    attributes = {}
    key = None
    for line in data.decode("utf-8").replace("\r\n", "\n").split("\n"):
        if line.startswith(" ") and key:
            attributes[key] += line[1:]
        elif ": " in line:
            key, value = line.split(": ", 1)
            attributes[key] = value
        else:
            key = None
    return attributes


def numeric_version(path):
    parts = re.findall(r"\d+", path.name)
    if not parts:
        raise SystemExit(f"Unrecognized Android SDK version directory: {path}")
    return tuple(int(part) for part in parts)


def write_entry(bundle, name, data):
    entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o100644 << 16
    bundle.writestr(entry, data)


def main():
    parser = argparse.ArgumentParser(
        description="Reduce a Morphe patches bundle to the YouTube Studio GmsCore patch."
    )
    parser.add_argument("--input", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--android-sdk", required=True, type=pathlib.Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    parsed_url = urllib.parse.urlparse(args.source_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
        or not re.fullmatch(r"/[^/]+/[^/]+", parsed_url.path.rstrip("/"))
    ):
        raise SystemExit("--source-url must be a GitHub repository HTTPS URL")
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        raise SystemExit("--version must use the numeric MAJOR.MINOR.PATCH format")

    sdk = args.android_sdk.expanduser().resolve()
    build_tools_root = sdk / "build-tools"
    platforms_root = sdk / "platforms"
    if not build_tools_root.is_dir() or not platforms_root.is_dir():
        raise SystemExit("Android SDK build-tools or platforms directory was not found")

    build_tools = max(
        (path for path in build_tools_root.iterdir() if path.is_dir()),
        key=numeric_version,
    )
    platforms = max(
        (path for path in platforms_root.iterdir() if path.is_dir()),
        key=numeric_version,
    )
    d8_jar = build_tools / "lib" / "d8.jar"
    android_jar = platforms / "android.jar"
    java = shutil.which("java")
    if not d8_jar.is_file() or not android_jar.is_file() or not java:
        raise SystemExit("Java, Android SDK D8, or android.jar was not found")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.input) as source:
        bad_entry = source.testzip()
        if bad_entry:
            raise SystemExit(f"Input bundle has a damaged entry: {bad_entry}")

        patcher_version = parse_manifest(source.read("META-INF/MANIFEST.MF")).get(
            "Patcher-Version"
        )
        if not patcher_version:
            raise SystemExit("Input bundle manifest has no Patcher-Version")
        if "extensions/shared.mpe" not in source.namelist():
            raise SystemExit("Input bundle does not contain the shared extension")

        class_entries = [
            item for item in source.infolist()
            if item.filename.endswith(".class")
            and any(item.filename.startswith(prefix) for prefix in CLASS_PREFIXES)
        ]
        patch_classes = [
            item.filename for item in class_entries
            if item.filename.startswith("app/morphe/patches/")
        ]
        unrelated = [
            name for name in patch_classes
            if not any(
                name.startswith(f"app/morphe/patches/{package}/")
                for package in ("all", "shared", "youtubestudio")
            )
        ]
        if unrelated:
            raise SystemExit(f"Reduced bundle contains unrelated patch classes: {unrelated}")
        if not any(
            item.filename.startswith("app/morphe/patches/youtubestudio/")
            for item in class_entries
        ):
            raise SystemExit("No YouTube Studio patch classes were found")

        with tempfile.TemporaryDirectory(prefix="studio-gmscore-mpp-") as temp:
            temp_path = pathlib.Path(temp)
            class_jar = temp_path / "studio-classes.jar"
            with zipfile.ZipFile(class_jar, "w", zipfile.ZIP_DEFLATED) as jar:
                for item in class_entries:
                    jar.writestr(item.filename, source.read(item.filename))

            classpath_jar = temp_path / "source-classes.jar"
            with zipfile.ZipFile(classpath_jar, "w", zipfile.ZIP_DEFLATED) as jar:
                for item in source.infolist():
                    if item.filename.endswith(".class"):
                        jar.writestr(item.filename, source.read(item.filename))

            dex_dir = temp_path / "dex"
            dex_dir.mkdir()
            subprocess.run(
                [
                    java, "-cp", str(d8_jar), "com.android.tools.r8.D8",
                    "--min-api", "26", "--lib", str(android_jar),
                    "--classpath", str(classpath_jar),
                    "--output", str(dex_dir), str(class_jar),
                ],
                check=True,
            )
            dex_file = dex_dir / "classes.dex"
            if not dex_file.is_file():
                raise SystemExit("D8 did not produce classes.dex")

            manifest = (
                "Manifest-Version: 1.0\r\n"
                "Name: YouTube Studio GmsCore Patch\r\n"
                "Description: GmsCore support for YouTube Studio, for use with Morphe Manager.\r\n"
                f"Version: {args.version}\r\n"
                f"Source: {args.source_url.rstrip('/')}\r\n"
                "Author: Community maintainers\r\n"
                f"Contact: {args.source_url.rstrip('/')}/issues\r\n"
                f"Website: {args.source_url.rstrip('/')}\r\n"
                "License: GNU General Public License v3.0\r\n"
                f"Patcher-Version: {patcher_version}\r\n\r\n"
            ).encode("utf-8")

            with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as bundle:
                write_entry(bundle, "META-INF/MANIFEST.MF", manifest)
                write_entry(
                    bundle,
                    "extensions/shared.mpe",
                    source.read("extensions/shared.mpe"),
                )
                for item in class_entries:
                    write_entry(bundle, item.filename, source.read(item.filename))
                write_entry(bundle, "classes.dex", dex_file.read_bytes())

    with zipfile.ZipFile(args.output) as bundle:
        if bundle.testzip():
            raise SystemExit("The generated bundle failed its ZIP integrity check")
    print(f"Wrote {args.output} with {len(class_entries)} selected class files")


if __name__ == "__main__":
    main()