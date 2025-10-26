"""Enhanced build script.

Usage:
  python build.py                 # copy root index.html or first *.html into dist/
  python build.py path/to/file.html
  python build.py path/to/site_dir  # copies contents of site_dir into dist/

The script will create (or clear) `dist/` and copy files. If dist already
contains HTML and no source is found, the script will treat the build as
already complete.
"""
from pathlib import Path
import shutil
import sys
import argparse


def clear_dir(path: Path):
	if path.exists():
		shutil.rmtree(path)
	path.mkdir(parents=True, exist_ok=True)


def copy_file_to_dist(src: Path, destdir: Path):
	destdir.mkdir(parents=True, exist_ok=True)
	shutil.copy2(src, destdir / src.name)


def copy_dir_to_dist(src_dir: Path, destdir: Path):
	# Clear destdir then copytree
	clear_dir(destdir)
	for item in src_dir.iterdir():
		dest = destdir / item.name
		if item.is_dir():
			shutil.copytree(item, dest)
		else:
			shutil.copy2(item, dest)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("source", nargs="?", help="source file or directory to copy into dist")
	args = parser.parse_args()

	root = Path(__file__).parent
	destdir = root / "dist"

	# If a source arg provided
	if args.source:
		src = Path(args.source)
		if not src.exists():
			print(f"Error: provided source '{src}' does not exist.")
			raise SystemExit(1)

		if src.is_file():
			copy_file_to_dist(src, destdir)
			print(f"Copied file {src} -> {destdir}")
			return
		if src.is_dir():
			copy_dir_to_dist(src, destdir)
			print(f"Copied directory {src} -> {destdir}")
			return

	# No source arg: look for root index.html or any html files
	src_root_index = root / "index.html"
	if src_root_index.exists():
		copy_file_to_dist(src_root_index, destdir)
		print(f"Build: copied {src_root_index.name} -> dist/")
		return

	candidates = list(root.glob("*.html"))
	if candidates:
		copy_file_to_dist(candidates[0], destdir)
		print(f"Build: copied {candidates[0].name} -> dist/")
		return

	# If nothing in root but dist already has html, treat as built
	existing = list(destdir.glob("*.html"))
	if existing:
		print(f"No source found in root; dist already contains {existing[0].name}. Build considered complete.")
		return

	# If there's a typical public/ or build/ folder, copy it
	for candidate_dir in (root / "public", root / "build", root / "site", root / "NNS-Real-Time-Translation"):
		if candidate_dir.exists() and candidate_dir.is_dir():
			copy_dir_to_dist(candidate_dir, destdir)
			print(f"Build: copied directory {candidate_dir} -> dist/")
			return

	print("Error: no source html or site directory found. Create index.html in project root or provide a source path to the script.")
	raise SystemExit(1)


if __name__ == "__main__":
	main()
