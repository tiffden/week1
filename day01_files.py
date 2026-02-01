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
    # Debugging
    # print(f"{type(dir_path)=}") # what class is this?
    # print(f"{dir(Path)=}") # discover object names (or scope dir_path)

    # these type declarations are optional but help code readability
    files: list[Path]
    sizes: list[int]
    files_sizes_unsorted: list[tuple[Path, int]]  # filename, size
    files_sorted: list[tuple[Path, int]]

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
        print("Informational: At least one empty file detected.")
    if all(size < 0 for size in sizes):
        print("Informational: All files have non-zero size.")

    files_sizes_unsorted = [
        (p, p.stat().st_size) for p in dir_path.iterdir() if p.is_file()
    ]

    # Sort by size (key=...)
    # lambda anonymous function aka function w/o name 'inlined here:'
    # versus:  files_sorted = sorted(files_sizes_unsorted, key=get_size)
    # or: keys = [t[1] for t in files_sizes_unsorted]
    #     files_sorted = sorted(files_sizes_unsorted, based_on=keys)
    # sorted passes key('a function') one element at a time, here a tuple
    files_sorted = sorted(files_sizes_unsorted, key=lambda t: t[1])  # key 2nd element

    # Unpacking + starred unpacking
    smallest, *middle, largest = files_sorted
    print(f"{smallest[0].name=}, {smallest[1]=}")
    print(f"{largest[0].name=}, {largest[1]=}")

    # zip + enumerate
    for i, (path, size) in enumerate(files_sorted, start=1):
        # i - counter, > right align, 2 width
        # filename, > left align, 30 width (max width 30)
        # size, > right align, 10 width
        print(f"{i:>2}. {path.name:<30.30} {size:>10,} bytes")


# __name__ is a built-in module attribute.
# Every Python file that is loaded gets a value for __name__.
# If run directly (python day01_files.py) → dunder main
# else if import day01_files.py → __name__ == "day01_files"
# python day01_files.py /tmp → dir_arg = Path("/tmp") -- you can give it a path as arg
if __name__ == "__main__":
    dir_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")  # current directory
    main(dir_arg)
