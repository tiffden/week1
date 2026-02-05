from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Iterable
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
    print(f"Origin:          {r.origin}")
    print("\nAdvice:")
    print(r.advice)
    print()


# -------------------------
# Symbol lookup
# -------------------------


@dataclass(frozen=True, slots=True)
class SymbolMatch:
    symbol: str
    found_in: str
    origin_module: str | None
    object_type: str
    source: str | None


def iter_stdlib_module_names() -> list[str]:
    names = sorted(getattr(sys, "stdlib_module_names", set()))
    return names


def find_symbol_matches(symbol: str, module_names: Iterable[str]) -> list[SymbolMatch]:
    matches: list[SymbolMatch] = []
    for mod_name in module_names:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue

        if not hasattr(mod, symbol):
            continue

        obj = getattr(mod, symbol)
        origin_module = getattr(obj, "__module__", None)
        obj_type = type(obj).__name__
        source = None
        try:
            source = inspect.getsourcefile(obj) or inspect.getfile(obj)
        except Exception:
            pass

        matches.append(
            SymbolMatch(
                symbol=symbol,
                found_in=mod.__name__,
                origin_module=origin_module,
                object_type=obj_type,
                source=source,
            )
        )

    return matches


def print_symbol_matches(symbol: str, matches: list[SymbolMatch]) -> None:
    print("\nSymbol lookup")
    print("=" * 30)
    print(f"Symbol: {symbol}")
    if not matches:
        print("No matches found in the standard library.")
        print("Tip: the symbol may live in a third-party package.")
        return

    for m in matches:
        print("-" * 30)
        print(f"Found in:     {m.found_in}")
        print(f"Origin:       {m.origin_module}")
        print(f"Object type:  {m.object_type}")
        print(f"Source:       {m.source}")


# -------------------------
# Entry point
# -------------------------


def main() -> None:
    try:
        choice = input("Look up a module or a symbol? (m/s): ").strip().lower()
        if not choice:
            raise ValueError("No choice provided")

        if choice in {"m", "module"}:
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

        elif choice in {"s", "symbol"}:
            symbol = input("Symbol to locate in the stdlib (e.g. ExitStack): ").strip()
            if not symbol:
                raise ValueError("No symbol provided")

            stdlib_names = iter_stdlib_module_names()
            if not stdlib_names:
                print("Stdlib module names are unavailable on this Python build.")
            else:
                matches = find_symbol_matches(symbol, stdlib_names)
                print_symbol_matches(symbol, matches)

        else:
            raise ValueError("Choice must be 'm' or 's'")

    except ModuleNotFoundError as e:
        print(f"ERROR: Module not found: {e.name}", file=sys.stderr)
        raise SystemExit(1) from e
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2) from e


if __name__ == "__main__":
    main()
