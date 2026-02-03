# You want a function that:
# 	1.	Validates shape fast (guard clauses).
# 	2.	Uses match to route behavior based on dict structure and values.
# 	3.	Demonstrates:
# 	•	guards (if ...)
# 	•	try/except/else/finally
# 	# •	EAFP vs LBYL

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


# --- Domain model (tiny, just for practice) ---------------------------------
@dataclass(frozen=True, slots=True)
class DispatchResult:
    ok: bool
    action: str
    detail: str


# --- Helpers ----------------------------------------------------------------
def _guard_is_dict(event: Any) -> dict[str, Any] | None:
    """Guard clause helper: we only dispatch dict events."""
    if not isinstance(event, dict):
        return None
    return event


def _parse_iso8601_utc(ts: str) -> datetime:
    """
    EAFP: try to parse first; if it fails, raise ValueError.
    Accepts e.g. "2026-02-02T12:34:56+00:00" or "...Z".
    """
    # Common "Z" suffix -> "+00:00"
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)  # may raise ValueError
    # Normalize to UTC if tz-aware; if naive, treat as UTC for this exercise.
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# --- Dispatcher --------------------------------------------------------------


def dispatch(event: Any) -> DispatchResult:
    """
    Parse + route an input "event" dict using match/case.
    Demonstrates:
      - guard clauses
      - match with destructuring + guards
      - EAFP parsing
      - try/except/else/finally
    """
    # Guard clause: reject non-dicts early.
    event_dict = _guard_is_dict(event)
    if event_dict is None:
        return DispatchResult(False, "reject", "event must be a dict")
    if not isinstance(event_dict.get("type"), str):
        return DispatchResult(False, "reject", "'type:' must start dict entry")

    # Optional guard clause: require a type (common in event envelopes).
    # LBYL example (simple and readable here): check presence before match.
    if "type" not in event_dict:
        return DispatchResult(False, "reject", "missing required key: 'type'")

    # Demonstrate try/except/else/finally around parsing/dispatch.
    # Keep the try block tight: only wrap the risky part.
    try:
        match event_dict:
            # 1) Simple shape match
            case {"type": "user.created", "id": user_id} if isinstance(user_id, int):
                if user_id > 0:
                    return DispatchResult(True, "create_user", f"user_id={user_id}")
                else:
                    return DispatchResult(False, "reject", "user_id must be positive")
            # 2) Destructure nested dict + guard
            case {
                "type": "order.paid",
                "order": {"id": order_id, "total": total},
                "paid_at": paid_at,
            } if isinstance(order_id, str) and isinstance(total, (int, float, str)):
                # EAFP: attempt parse, raise if invalid
                paid_dt = _parse_iso8601_utc(str(paid_at))

                return DispatchResult(
                    True,
                    "mark_order_paid",
                    f"order_id={order_id} paid_at={paid_dt.isoformat()}",
                )

            # 3) Tuple/list shape (another common reason to use match)
            case {"type": "email.send", "to": [*recipients]} if recipients:
                # recipients becomes a list
                if not all(isinstance(r, str) and "@" in r for r in recipients):
                    return DispatchResult(False, "reject", "invalid recipients list")
                return DispatchResult(
                    True, "send_email", f"recipients={len(recipients)}"
                )

            # 4) Unknown type (fallback)
            case {"type": t}:
                return DispatchResult(False, "ignore", f"unknown event type: {t!r}")

            # 5) Dict but no matching shape (fallback)
            case _:
                return DispatchResult(False, "reject", "unrecognized event shape")

    except ValueError as e:
        # Parse errors (e.g., invalid ISO timestamp)
        return DispatchResult(False, "reject", f"value error: {e}")

    except Exception as e:
        # Catch-all for learning; in real code, be more specific.
        return DispatchResult(
            False, "error", f"unexpected error: {type(e).__name__}: {e}"
        )

    else:
        # Usually you don't need else if you always return inside try;
        # but included to demonstrate the construct.
        return DispatchResult(True, "noop", "no action needed")

    finally:
        # Demonstration only: finally is for cleanup (files, locks, etc.).
        # Avoid noisy prints in libraries; OK in a script.
        pass


def main() -> None:
    # create a mixture of test events
    events: list[Any] = [
        {"type": "user.created", "id": 123},
        {"type": "user.created", "id": -1},
        {
            "type": "order.paid",
            "order": {"id": "A100", "total": "19.95"},
            "paid_at": "2026-02-02T10:15:00Z",
        },
        {
            "type": "order.paid",
            "order": {"id": "A101", "total": 20},
            "paid_at": "not-a-date",
        },
        {"type": "email.send", "to": ["a@example.com", "b@example.com"]},
        {"type": "email.send", "to": []},
        {"type": "unknown.event-o-matic", "x": 1},
        ["not", "a", "dict"],
        {"id": "type"},
        {"type": "user.created", "type2": 14},
        {"type": 666, "id": 123},
    ]

    for i, ev in enumerate(events, start=1):
        result = dispatch(ev)
        print(
            f"{i:>2}. ok={result.ok:<5}"
            f"action={result.action:<15} detail={result.detail}"
        )


if __name__ == "__main__":
    print("*********** Dispatch Demo *************")
    main()
