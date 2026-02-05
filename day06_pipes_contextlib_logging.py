from __future__ import annotations

import csv
import json
import logging
import sys
from collections.abc import Iterable
from contextlib import ExitStack
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

# -------------------------
# How this maps to the Day 6 targets
# 	•	with open(...): used via Path.open() inside ExitStack (still a with pattern).
# 	•	ExitStack: manages input & output file handles together;
#           this gives no leaks even on exceptions.
# 	•	Custom exceptions: PipelineError subclasses with clear intent.
# 	•	Narrow exception handling:
# 	•	parses integers with except ValueError
# 	•	parses decimals with except (InvalidOperation, ValueError)
# 	•	output writes with except OSError
# 	•	raise ... from e: used in parsing and IO layers to preserve the causal chain.
# 	•	logging vs print: logs start/end, parameters, failure; print is never used.
# -------------------------


# -------------------------
# Custom exceptions (meaningful + composable)
# Exception names are classes, and class names use CapWords
# -------------------------


# Exception is a built-in
class PipelineErr(Exception):
    """Base class for all pipeline errors."""


class InputNotFoundErr(PipelineErr):
    """Raised when the input file does not exist."""


class InputFormatErr(PipelineErr):
    """Raised when the input file is unreadable or structurally invalid."""


class ValidationErr(PipelineErr):
    """Raised when data validation fails."""

    def __init__(self, message: str, *, line_no: int | None = None) -> None:
        super().__init__(message)
        self.line_no = line_no


class OutputWriteErr(PipelineErr):
    """Raised when writing output artifacts fails."""


# -------------------------
# Domain model
# -------------------------


@dataclass(frozen=True, slots=True)
class Row:
    sku: str
    qty: int
    unit_price: Decimal  # in dollars

    def __str__(self) -> str:
        return f"sku: {self.sku}  qty: {self.qty} unit_price: {self.unit_price}"


@dataclass(frozen=True, slots=True)
class Stats:
    rows_in: int
    rows_out: int
    total_qty: int
    gross_revenue: Decimal


# -------------------------
# Logging setup
# -------------------------

# basicConfig
# 1.	Creates a root logger handler
# 2.	Attaches a StreamHandler
# 3.	Sets that handler to write to sys.stderr (not stdout)
# 4.    level can be one of: DEBUG INFO WARNING ERROR CRITICAL
#
# formating using % - This is Python logging’s format-string mini-language.
# It predates f-strings and is specific to the logging module,
# logging.Formatter parses it, it specifies what from the LogRecord to use
# general form:  %(field_name)format_spec
#   %(asctime)s
#   •	Human-readable timestamp
#   •	Default format: YYYY-MM-DD HH:MM:SS,mmm
#   •	Derived from record.created
#   %(name)s
#   • Logger name - here it will be day06.pipeline
#
# Usage:
#   log = logging.getLogger("day06.pipeline")
#   log.warning("bad input: %r", value)
#
# Handlers
#   handlers=[logging.StreamHandler(sys.stdout)] - mix it in with print()
#   Logging handlers own their resources.
#   A FileHandler opens the file when it’s created and closes it when:
# •   the handler is explicitly closed, or
# •   the Python process shuts down normally;
# •   therefore it doesn't need to be in ExitStack
LOGGER_NAME = "day06.pipeline"
log = logging.getLogger(LOGGER_NAME)


def configure_logging(level: int = logging.INFO) -> None:
    # root = logging.getLogger(LOGGER_NAME)
    log.setLevel(level)

    if log.handlers:
        return  # prevent duplicate handlers if called twice

    log_path = Path("logs/day06_pipes.log")
    log_path.parent.mkdir(exist_ok=True)

    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    formatter = logging.Formatter(fmt)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    log.addHandler(console_handler)


# -------------------------
# Parsing + validation
# -------------------------

REQUIRED_COLUMNS = {"sku", "qty", "unit_price"}


# generator function:  Any function that contains a yield statement
# Because it contains yield, calling it does not execute the body immediately
# Instead, it returns a generator object.
def parse_rows(reader: csv.DictReader) -> Iterable[Row]:
    # Validate header shape early (input format error)
    if reader.fieldnames is None:
        raise InputFormatErr("CSV has no header row (fieldnames missing).")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise InputFormatErr(f"CSV missing required columns: {sorted(missing)}")

    for i, raw in enumerate(reader, start=2):  # start=2 because header is line 1
        # Exceptions inside a generator are raised during iteration, not at creation
        # this is why try is within the loop
        try:
            # Check 1
            sku = (raw.get("sku") or "").strip()
            if not sku:
                raise ValidationErr("sku must be non-empty", line_no=i)

            # Check 2
            qty_s = (raw.get("qty") or "").strip()
            try:
                qty = int(qty_s)
            except ValueError as e:
                raise ValidationErr(
                    f"qty must be an integer (got {qty_s!r})", line_no=i
                ) from e

            # Check 3
            if qty <= 0:
                raise ValidationErr("qty must be > 0", line_no=i)

            # Check 4
            price_s = (raw.get("unit_price") or "").strip()
            try:
                unit_price = Decimal(price_s)
            except (InvalidOperation, ValueError) as e:
                raise ValidationErr(
                    f"unit_price must be a decimal number (got {price_s!r})",
                    line_no=i,
                ) from e

            # Check 5
            if unit_price < 0:
                raise ValidationErr("unit_price must be >= 0", line_no=i)

            # Passed the checks, return the row
            yield Row(sku=sku, qty=qty, unit_price=unit_price)

        # Deal with any raised custom errors
        except ValidationErr as e:
            log.warning("*** Validation failed on line %s", e.line_no)
            log.warning(f"*** {e}")
            continue


# -------------------------
# Pipeline
# -------------------------


def run_pipeline(input_csv: Path, out_clean_csv: Path, out_stats_json: Path) -> Stats:
    """
    Reads input CSV -> validates + normalizes -> writes cleaned CSV + stats JSON.

    Raises:
        InputNotFoundError, InputFormatError, ValidationError, OutputWriteError
    """
    log.info("Starting pipeline")
    log.info("Input: %s", input_csv)
    log.info("Outputs: %s, %s", out_clean_csv, out_stats_json)

    if not input_csv.exists():
        raise InputNotFoundErr(f"Input file not found: {input_csv}")

    # Ensure output dirs exist
    out_clean_csv.parent.mkdir(parents=True, exist_ok=True)
    out_stats_json.parent.mkdir(parents=True, exist_ok=True)

    rows_in = 0
    rows_out = 0
    total_qty = 0
    gross = Decimal("0")

    try:
        # ExitStack keeps multiple open resources safe and tidy
        #   All opened files will automatically be closed at the end of
        #   the with statement, even if attempts to open files later
        #   in the list raise an exception.
        with ExitStack() as stack:
            fin = stack.enter_context(input_csv.open("r", newline="", encoding="utf-8"))
            fout_csv = stack.enter_context(
                out_clean_csv.open("w", newline="", encoding="utf-8")
            )
            # Write JSON at the end to avoid partial stats if validation fails early.

            reader = csv.DictReader(fin)
            writer = csv.DictWriter(fout_csv, fieldnames=["sku", "qty", "unit_price"])
            writer.writeheader()

            for row in parse_rows(reader):
                rows_in += 1
                rows_out += 1
                total_qty += row.qty
                gross += Decimal(row.qty) * row.unit_price

                log.info(row)
                writer.writerow(
                    {"sku": row.sku, "qty": row.qty, "unit_price": str(row.unit_price)}
                )

            stats = Stats(
                rows_in=rows_in,
                rows_out=rows_out,
                total_qty=total_qty,
                gross_revenue=gross,
            )

        # Write stats after all file handles were safely closed.
        try:
            # JSON is a text serialization format, not a Python data structure
            # json.load - reads file  json.dump - writes file
            # JSON supports only:
            # •	objects → Python dict
            # •	arrays → Python list
            # •	strings, numbers, booleans, null
            # (Stats dataclass contains a Decimal, which JSON cannot encode
            #    need to turn it into a string for serialization)
            out_stats_json.write_text(
                json.dumps(
                    {
                        "rows_in": stats.rows_in,
                        "rows_out": stats.rows_out,
                        "total_qty": stats.total_qty,
                        "gross_revenue": str(
                            stats.gross_revenue
                        ),  # DECIMAL not in JSON
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            raise OutputWriteErr(f"Failed to write stats JSON: {out_stats_json}") from e

        log.info(
            "Processing Completed: rows_out=%d total_qty=%d gross=%s",
            rows_out,
            total_qty,
            gross,
        )
        return stats

    except OSError as e:
        # Narrow-ish: OSError covers file IO issues; we preserve cause.
        raise InputFormatErr(f"File IO failed while processing {input_csv}") from e


# -------------------------
# Minimal CLI entry point (optional)
# -------------------------


def main() -> None:
    # Top-level imports run at import time VERSUS
    # Code inside main() runs only when the program is executed as a script
    # Everything CLI-ish belongs in main()
    import argparse

    configure_logging()
    log.info("starting log")

    # USAGE EXAMPLE FROM argparse.py
    # parser = argparse.ArgumentParser(
    #     description='sum the integers at the command line')
    # parser.add_argument(
    #     'integers', metavar='int', nargs='+', type=int,
    #     help='an integer to be summed')
    # parser.add_argument(
    #     '--log', default=sys.stdout, type=argparse.FileType('w'),
    #     help='the file where the sum should be written')
    # args = parser.parse_args()
    # args.log.write('%s' % sum(args.integers))
    # args.log.close()

    p = argparse.ArgumentParser(description="Day 6 file-processing pipeline")

    p.add_argument("input_csv", type=Path, nargs="?")  # optional
    p.add_argument("--out-clean", type=Path, default=Path("out/clean.csv"))
    p.add_argument("--out-stats", type=Path, default=Path("out/stats.json"))
    args = p.parse_args()

    if args.input_csv is None:
        user_input = input("Input CSV path: ").strip()
        if not user_input:
            print("Input CSV path is required.")
            raise SystemExit(2)
        args.input_csv = Path(user_input)

    try:
        run_pipeline(args.input_csv, args.out_clean, args.out_stats)
    except PipelineErr as e:
        # log.exception prints stack trace; helpful during development.
        log.exception("Pipeline failed: %s", e)
        print("Pipeline failed, see log.")
        raise SystemExit(2) from e


if __name__ == "__main__":
    main()
