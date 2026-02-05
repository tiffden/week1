from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from itertools import islice, tee

# ----------------------------
# Clasic GENERATOR usages:
# 1. File streaming. - for line in open("huge_log_file.txt"): ...
# 2. API pagination. - while more_pages: fetch_next_page() ...
# 3. Infinite sequences. - count(), cycle(), repeat() from itertools
# 4. Coroutines - (old code: .send()/yield) for cooperative multitasking
# 4b. Async generators - async for ... in ... : for I/O-bound concurrency, await
# 5. Memory efficiency for large datasets - sum, count, filter, stats, etc.
# 6. Producer-consumer patterns with threads
# ----------------------------

# ----------------------------
# EFFICIENCY with GENERATORS
# Efficiency = time + memory + clarity (for 1 million events, memory matters)
# Streaming versus materializing into a list (streaming is the default)
# one pass is king - do everything in a single loop (counts, status, sums, etc.)
# batching is good when writing to database or API in chunks, reduces I/O calls
# batching doesn't do much for Python-internal processing speed
# Avoid accidental list materialization - sorted(huge_generator) makes a list!
# Keep it simple - sum, count; avoid heavy CPU per item in the generator
# ----------------------------

# ----------------------------
# TYPICAL PATTERN:
# Generator reads data (file, API, queue, DB cursor)
# Generator filters/transforms
# Batch writes to DB (or yields rows from DB)
#
# Common use cases:
# Read from DB cursor: DB drivers yield rows one at a time (generator style)
# Write in batches: stream events → insert 1,000 rows at a time
# Lookup keys: for speed pre‑load a small lookup table in memory if small enough
#
# ----------------------------


@dataclass(frozen=True, slots=True)
class Event:
    user_id: int
    kind: str  # "view", "purchase", "refund"
    amount_cents: int  # 0 for views


def generator_make_events(n: int) -> Iterator[Event]:
    """
    Streaming source: yields events one at a time.
    This is the pattern you'd use for reading a huge file, API pages, etc.
    """
    kinds = ("view", "view", "view", "purchase", "refund", "purchase", "refund")
    for i in range(n):
        kind = kinds[i % len(kinds)]  # cycling kinds, a%b "left over after div"
        amt = 0
        if kind == "purchase":
            amt = 400_00

        elif kind == "refund":
            amt = -100_00
        yield Event(user_id=i % 10, kind=kind, amount_cents=amt)


# ----------------------------
# “This function knows how to filter, but not what to filter.”
# backbone of:
# 	•	Functional pipelines
# 	•	Middleware
# 	•	Validators
# 	•	Authorization rules
# 	•	Query engines
# ----------------------------
def filter_events(
    events: Iterable[Event],
    predicate: Callable[[Event], bool],
) -> Iterator[Event]:
    for e in events:
        if predicate(e):
            yield e


def consume_and_summarize_events(events: Iterable[Event]) -> tuple[int, int, int]:
    purchase_amount: int = 0
    purchaser_count: int = 0
    refund_count: int = 0

    for e in filter_events(events, lambda ev: ev.kind in ("purchase", "refund")):
        if e.kind == "purchase":
            purchase_amount += e.amount_cents
            purchaser_count += 1
        elif e.kind == "refund":
            purchase_amount += e.amount_cents
            refund_count += 1

    return purchase_amount, purchaser_count, refund_count


def main() -> None:
    n = 10_000
    events_big = generator_make_events(n)

    # this can use a lot of memory if n is huge and
    # the iterators don't advance at the same pace
    # if one iterator races ahead and the other lags, buffer grows without bound
    # you should stop using events_big directly. The original events_big is still
    # the source iterator, but it’s now owned by the tee machinery.
    #     When is it exhausted?
    # It gets exhausted as a and/or b pull from it. In other words:
    # If you iterate a or b, tee pulls from events_big as needed.
    # Once both a and b have advanced past all items, the source is exhausted.
    a, b = tee(events_big)  # create two independent iterators from one

    print("----------")
    print(f"*******. Generated {n:,} events in a generator *******")
    print("----------")

    # LIST consumes the first 5 events in the generator
    # After that, events_big is still the same generator, but it now starts at event #5
    # consume_and_summarize_events - consumes the list (not the generator)
    first_five = list(islice(a, 5))
    amt1, count1, refund1 = consume_and_summarize_events(first_five)
    print(
        "PARTIALLY Consumed list(islice(a, 5) ->",
        f"${amt1 / 100:,.2f}",
        "Purchaser Count:",
        f"{count1:,}",
        "Refund Count:",
        f"{refund1:,}",
    )

    # consumes the rest of the events in the generator
    amt2, count2, refund2 = consume_and_summarize_events(a)
    print(
        "FULLY Consumed consume_and_summarize_events(a) ->",
        f"${amt2 / 100:,.2f}",
        "Purchaser Count:",
        f"{count2:,}",
        "Refund Count:",
        f"{refund2:,}",
    )

    # Nothing left to consume here; events_big is exhausted
    amt3, count3, refund3 = consume_and_summarize_events(a)
    print(
        "EXHAUSTED consume_and_summarize_events(a) ->",
        f"${amt3 / 100:,.2f}",
        "Purchaser Count:",
        f"{count3:,}",
        "Refund Count:",
        f"{refund3:,}",
    )

    # Entire list again from the second iterator
    amt4, count4, refund4 = consume_and_summarize_events(b)
    print(
        "SECOND ITERATOR consume_and_summarize_events(b) ->",
        f"${amt4 / 100:,.2f}",
        "Purchaser Count:",
        f"{count4:,}",
        "Refund Count:",
        f"{refund4:,}",
    )

    # Sanity Check
    total_purchases = count4 * 400_00
    total_refunds = refund4 * -100_00
    expected_total = total_purchases + total_refunds

    print(
        "SANITY CHECK: ",
        f"Purchases based on Count*400: ${total_purchases / 100:,.2f}",
        f"Refunds based on Count*100: ${total_refunds / 100:,.2f}",
        f"Expected Total: ${expected_total / 100:,.2f}",
    )


if __name__ == "__main__":
    main()
