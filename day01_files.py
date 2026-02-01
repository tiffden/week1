"""
Week 1 - Day 1
Explore pathlib, file sizes, sorting, enumerate, zip
"""

# 	•	reads a directory using Path; Path → modern, readable, cross-platform
# 	•	prints file sizes using f-strings; f"{var=}" → fast w/o debugger
# 	•	sorts by size
# 	•	uses enumerate and zip; zip(strict=True) → defensive programming
#  	•	unpacking → expressive data handling
# 	•	truthiness + any/all → Pythonic logic, fewer bugs

# pathlib.Path instead of os.path
# 	•	Path(".".iterdir()
import sys
from pathlib import Path


def main(dir_path: Path) -> None:
    print(f"Directory: {dir_path.absolute()=}")

    # Read directory (Path, not os.path)
    files = [p for p in dir_path.iterdir() if p.is_file()]

    # Truthiness + any/all
    if len(files) < 2:
        print("Need at least 2 files to make a sorted list.")
        return

    # •	p.stat().st_size
    sizes = [p.stat().st_size for p in files]
    print(f"{sizes=}")  # f-string with =

    if any(size == 0 for size in sizes):
        print("!! At least one empty file detected.")
    if all(size < 0 for size in sizes):
        print("All files nave non-zero size.")

    # Sort by size (key=...)
    files_with_sizes = [
        (p, p.stat().st_size) for p in dir_path.iterdir() if p.is_file()
    ]
    files_sorted = sorted(files_with_sizes, key=lambda t: t[1])

    # Unpacking + starred unpacking ?
    smallest, *middle, largest = files_sorted
    print(f"{smallest[0].name=}, {largest[0].name=}")

    # zip + enumerate
    for i, (path, size) in enumerate(files_with_sizes, start=1):
        print(f"{i:>2}. {path.name:<30} {size:>10,} bytes")


if __name__ == "__main__":
    dir_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")  # current directory
    main(dir_arg)
