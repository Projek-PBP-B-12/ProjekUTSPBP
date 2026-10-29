"""Build CSS halaman menggunakan standalone Tailwind CLI 4.3.3."""
import argparse
import hashlib
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent
WINDOWS_CLI = ROOT / ".tools/tailwindcss-v4.3.3-windows-x64.exe"
WINDOWS_SHA256 = "e0e260ce048014e9268f6237ff18f8ccf02cef521cbd0ae04e82c2cdf7aa3955"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=WINDOWS_CLI)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--page", choices=("app", "sharedpost", "dashboard"), default="sharedpost")
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    if not compiler.is_file():
        parser.error("Compiler tidak ditemukan. Ikuti SharedPost/STYLING.md untuk menyiapkannya.")
    if compiler == WINDOWS_CLI.resolve():
        digest = hashlib.sha256(compiler.read_bytes()).hexdigest()
        if digest != WINDOWS_SHA256:
            parser.error("Checksum compiler tidak cocok dengan versi yang digunakan proyek.")
    command = [
        str(compiler), "-i", f"assets/css/{args.page}.tailwind.css",
        "-o", f"static/css/{args.page}.css", "--minify",
    ]
    if args.watch:
        command.append("--watch")
    try:
        return subprocess.call(command, cwd=ROOT)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
