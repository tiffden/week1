from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterable
from contextlib import ExitStack
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

# -------------------------
# Custom exceptions (meaningful + composable)
# -------------------------


class PipelineError(Exception):
    """Base class for all pipeline errors."""


class InputNotFoundError(PipelineError):
    """Raised when the input file does not exist."""


class InputFormatError(PipelineError):
    """Raised when the input file is unreadable or structurally invalid."""


class ValidationError(PipelineError):
    """Raised when data validation fails."""

    def __init__(self, message: str, *, line_no: int | None = None) -> None:
        super().__init__(message)
        self.line_no = line_no


class OutputWriteError(PipelineError):
    """Raised when writing output artifacts fails."""


# -------------------------
# Domain model
# -------------------------


@dataclass(frozen=True, slots=True)
class Row:
    sku: str
    qty: int
    unit_price: Decimal  # in dollars


@dataclass(frozen=True, slots=True)
class Stats:
    rows_in: int
    rows_out: int
    total_qty: int
    gross_revenue: Decimal


# -------------------------
# Logging setup
# -------------------------


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


log = logging.getLogger("day06.pipeline")


# -------------------------
# Parsing + validation
# -------------------------

REQUIRED_COLUMNS = {"sku", "qty", "unit_price"}


def parse_rows(reader: csv.DictReader) -> Iterable[Row]:
    # Validate header shape early (input format error)
    if reader.fieldnames is None:
        raise InputFormatError("CSV has no header row (fieldnames missing).")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise InputFormatError(f"CSV missing required columns: {sorted(missing)}")

    for i, raw in enumerate(reader, start=2):  # start=2 because header is line 1
        try:
            sku = (raw.get("sku") or "").strip()
            if not sku:
                raise ValidationError("sku must be non-empty", line_no=i)

            qty_s = (raw.get("qty") or "").strip()
            try:
                qty = int(qty_s)
            except ValueError as e:
                raise ValidationError(
                    f"qty must be an integer (got {qty_s!r})", line_no=i
                ) from e
            if qty <= 0:
                raise ValidationError("qty must be > 0", line_no=i)

            price_s = (raw.get("unit_price") or "").strip()
            try:
                unit_price = Decimal(price_s)
            except (InvalidOperation, ValueError) as e:
                raise ValidationError(
                    f"unit_price must be a decimal number (got {price_s!r})",
                    line_no=i,
                ) from e
            if unit_price < 0:
                raise ValidationError("unit_price must be >= 0", line_no=i)

            yield Row(sku=sku, qty=qty, unit_price=unit_price)
        except ValidationError:
            # Re-raise as-is (already meaningful and annotated)
            raise


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
        raise InputNotFoundError(f"Input file not found: {input_csv}")

    # Ensure output dirs exist (resource hygiene + ergonomics)
    out_clean_csv.parent.mkdir(parents=True, exist_ok=True)
    out_stats_json.parent.mkdir(parents=True, exist_ok=True)

    rows_in = 0
    rows_out = 0
    total_qty = 0
    gross = Decimal("0")

    try:
        # ExitStack keeps multiple open resources safe and tidy
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
            out_stats_json.write_text(
                json.dumps(
                    {
                        "rows_in": stats.rows_in,
                        "rows_out": stats.rows_out,
                        "total_qty": stats.total_qty,
                        "gross_revenue": str(stats.gross_revenue),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            raise OutputWriteError(
                f"Failed to write stats JSON: {out_stats_json}"
            ) from e

        log.info("Done. rows_out=%d total_qty=%d gross=%s", rows_out, total_qty, gross)
        return stats

    except OSError as e:
        # Narrow-ish: OSError covers file IO issues; we preserve cause.
        raise InputFormatError(f"File IO failed while processing {input_csv}") from e


# -------------------------
# Minimal CLI entry point (optional)
# -------------------------


def main() -> None:
    import argparse

    configure_logging()

    p = argparse.ArgumentParser(description="Day 6 file-processing pipeline")
    p.add_argument("input_csv", type=Path)
    p.add_argument("--out-clean", type=Path, default=Path("out/clean.csv"))
    p.add_argument("--out-stats", type=Path, default=Path("out/stats.json"))
    args = p.parse_args()

    try:
        run_pipeline(args.input_csv, args.out_clean, args.out_stats)
    except PipelineError as e:
        # log.exception prints stack trace; helpful during development.
        log.exception("Pipeline failed: %s", e)
        raise SystemExit(2) from e


if __name__ == "__main__":
    main()
