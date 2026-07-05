"""Build a minimal GitHub Pages artifact for the Kodi repository."""

import re
import shutil
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent
SITE = ROOT / "_site"
ZIPS = ROOT / "addons" / "zips"
TEST_ZIP_PATTERN = re.compile(
    r"(?:-test-[0-9]+|~test[0-9]+|\.test-[0-9.]+)\.zip$"
)


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def repository_package_path(addon):
    for extension in addon.findall("extension"):
        if extension.get("point") not in (
            "xbmc.addon.metadata",
            "kodi.addon.metadata",
        ):
            continue

        package_path = extension.findtext("path")
        if package_path:
            return PurePosixPath(package_path)

    raise ValueError("Missing package path for {}".format(addon.get("id")))


def validate_package_path(addon_id, package_path):
    if (
        package_path.is_absolute()
        or ".." in package_path.parts
        or len(package_path.parts) != 2
        or package_path.parts[0] != addon_id
    ):
        raise ValueError(
            "Invalid package path for {}: {}".format(addon_id, package_path)
        )


def copy_addon_metadata(addon_id):
    source_dir = ZIPS / addon_id
    if not source_dir.is_dir():
        raise FileNotFoundError("Missing metadata directory: {}".format(source_dir))

    for source in source_dir.rglob("*"):
        if source.is_file() and source.suffix.lower() != ".zip":
            copy_file(source, SITE / "addons" / "zips" / source.relative_to(ZIPS))


def build_site():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)

    copy_file(ROOT / "index.html", SITE / "index.html")
    (SITE / ".nojekyll").touch()

    for installer in sorted(ROOT.glob("repository.*.zip")):
        if not TEST_ZIP_PATTERN.search(installer.name):
            copy_file(installer, SITE / installer.name)

    for filename in ("addons.xml", "addons.xml.md5"):
        copy_file(ZIPS / filename, SITE / "addons" / "zips" / filename)

    addons = ElementTree.parse(ZIPS / "addons.xml").getroot()
    package_count = 0
    for addon in addons.findall("addon"):
        addon_id = addon.get("id")
        if not addon_id:
            raise ValueError("Repository entry is missing an add-on id")

        package_path = repository_package_path(addon)
        validate_package_path(addon_id, package_path)

        source = ZIPS.joinpath(*package_path.parts)
        if not source.is_file():
            raise FileNotFoundError("Missing referenced package: {}".format(source))

        copy_addon_metadata(addon_id)
        copy_file(source, SITE / "addons" / "zips" / Path(*package_path.parts))
        package_count += 1

    total_size = sum(path.stat().st_size for path in SITE.rglob("*") if path.is_file())
    print(
        "Built {} with {} packages ({:.1f} MiB)".format(
            SITE, package_count, total_size / (1024 * 1024)
        )
    )


if __name__ == "__main__":
    build_site()
