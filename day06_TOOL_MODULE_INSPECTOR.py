from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

# -------------------------
# Data model
# -------------------------


@dataclass(frozen=True, slots=True)
class ModuleReport:
    name: str
    kind: str
    location: str
    readable_source: bool
    advice: str
    loader: str | None
    origin: str | None


# -------------------------
# Classification logic
# -------------------------


def classify_module(mod: ModuleType) -> ModuleReport:
    name = mod.__name__

    file = getattr(mod, "__file__", None)
    spec = getattr(mod, "__spec__", None)
    loader = type(spec.loader).__name__ if spec and spec.loader else None
    origin = spec.origin if spec else None

    # Built-in module
    if file is None:
        return ModuleReport(
            name=name,
            kind="built-in module (compiled into interpreter)",
            location="(no file on disk)",
            readable_source=False,
            advice=(
                "This module is built into the Python interpreter.\n"
                "Read CPython source under `Python/` or `Modules/` in the CPython repo."
            ),
            loader=loader,
            origin=origin,
        )

    path = Path(file)

    # Pure Python
    if path.suffix == ".py":
        loc = str(path)
        mr = ModuleReport(
            name=name,
            kind="pure Python module",
            location=loc,
            readable_source=True,
            advice=(f"Open the .py file in your editor:\nbash>code {loc}\n"),
            loader=loader,
            origin=origin,
        )
        return mr

    # Compiled extension
    if path.suffix in {".so", ".pyd", ".dll"}:
        return ModuleReport(
            name=name,
            kind="compiled extension module (C/C++)",
            location=str(path),
            readable_source=False,
            advice=(
                "This is a compiled binary extension.\n"
                "To read the implementation:\n"
                "• Find the module name in the CPython repository\n"
                "• Look under `Modules/` (e.g. math → mathmodule.c)\n"
                "• Use `help(module)` for the public API\n"
                "      bash> python\n"
                f"      import {name}\n"
                f"      help({name})\n"
                " • SPACE → next page\n"
                " • b → back\n"
                " • /sin → search\n"
                " • q → (exits help); Ctrl-d → exits python\n"
            ),
            loader=loader,
            origin=origin,
        )

    # Fallback / unusual case
    return ModuleReport(
        name=name,
        kind="unknown or non-standard module type",
        location=str(path),
        readable_source=False,
        advice=(
            "Inspect __spec__ and loader; may be zipimport, namespace pkg,"
            "or custom loader."
        ),
        loader=loader,
        origin=origin,
    )


# -------------------------
# Reporting
# -------------------------


def print_report(r: ModuleReport) -> None:
    print("\nModule inspection report")
    print("=" * 30)
    print(f"Name:            {r.name}")
    print(f"Type:            {r.kind}")
    print(f"Location:        {r.location}")
    print(f"Readable source: {'yes' if r.readable_source else 'no'}")
    print(f"Loader:          {r.loader}")
    print(f"Location:        {r.origin}")
    print("\nAdvice:")
    print(r.advice)
    print()


# -------------------------
# Entry point
# -------------------------


def main() -> None:
    try:
        name = input("Module name to inspect (e.g. math, pathlib): ").strip()
        if not name:
            raise ValueError("No module name provided")

        mod = importlib.import_module(name)

        # Extra signal: can inspect.getsource succeed?
        try:
            inspect.getsource(mod)
        except (OSError, TypeError):
            pass  # expected for non-Python modules

        report = classify_module(mod)
        print_report(report)

    except ModuleNotFoundError as e:
        print(f"ERROR: Module not found: {e.name}", file=sys.stderr)
        raise SystemExit(1) from e
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2) from e


if __name__ == "__main__":
    main()
