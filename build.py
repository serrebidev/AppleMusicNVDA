"""Build the installable add-on using only Python's standard library."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import hashlib
import re


def build():
    root = Path(__file__).resolve().parent
    source = root / "addon"
    manifest = (source / "manifest.ini").read_text(encoding="utf-8")
    version = re.search(r"^version = ([\d.]+)$", manifest, re.MULTILINE).group(1)
    output = root / "dist" / f"AppleMusic-{version}.nvda-addon"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(source).as_posix())
        archive.write(root / "LICENSE", "LICENSE")
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert {"manifest.ini", "appModules/applemusic.py", "doc/en/readme.html", "LICENSE"} <= set(archive.namelist())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(output)
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    build()
