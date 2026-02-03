from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import chain, islice, pairwise

# ----------------------------
# Sample dataset (pretend this is large)
# ----------------------------


@dataclass(frozen=True, slots=True)
class Event:
    user_id: int
    kind: str  # "view", "purchase", "refund"
    amount_cents: int  # 0 for views
    ts: int  # counter used as a "pretend int timestamp" for simplicity


def make_events(n: int) -> Iterator[Event]:
    """
    Streaming source: yields events one at a time.
    This is the pattern you'd use for reading a huge file, API pages, etc.
    """
    kinds = ("view", "view", "view", "purchase", "refund")
    for i in range(n):
        kind = kinds[i % len(kinds)]  # cycling kinds, a%b "left over after div"
        amt = 0
        if kind == "purchase":
            amt = 500 + (i % 7) * 100
        elif kind == "refund":
            amt = -200
        yield Event(user_id=i % 10, kind=kind, amount_cents=amt, ts=i)


# ----------------------------
# 1) Comprehensions: readable transforms
# ----------------------------


def comprehension_examples(events: Iterable[Event]) -> None:
    # List comprehension: select + transform
    purchase_amounts = [e.amount_cents for e in events if e.kind == "purchase"]

    # Set comprehension: unique user_ids who purchased
    purchaser_ids = {e.user_id for e in events if e.kind == "purchase"}

    # Dict comprehension: last timestamp we saw per user_id
    # (If multiple events for a user, later keys overwrite earlier keys.)
    last_seen_ts = {e.user_id: e.ts for e in events}

    print("purchase_amounts[:5] =", purchase_amounts[:5])
    print("purchaser_ids =", sorted(purchaser_ids))
    print("last_seen_ts[0..3] =", {k: last_seen_ts[k] for k in range(4)})


# Readability rule demo:
# If you need nested loops + conditions + transforms, prefer an explicit loop.
def too_complex_as_comprehension(events: Iterable[Event]) -> dict[int, int]:
    """
    Sum purchase amount per user, ignoring refunds and views.
    This *can* be done with clever comprehensions, but a loop is clearer.
    """
    totals: dict[int, int] = {}
    for e in events:
        if e.kind != "purchase":
            continue
        totals[e.user_id] = totals.get(e.user_id, 0) + e.amount_cents
    return totals


# ----------------------------
# 2) Generator expressions: streaming pipelines
# ----------------------------


def streaming_pipeline(events: Iterable[Event]) -> int:
    """
    Sum purchase cents without ever building a list of purchases.
    """
    purchase_cents = (e.amount_cents for e in events if e.kind == "purchase")
    return sum(purchase_cents)


# ----------------------------
# 3) yield basics: writing your own generator
# ----------------------------


# *kinds is a variable-length argument list
def only_kinds(events: Iterable[Event], *kinds: str) -> Iterator[Event]:
    """
    yield-based filter: produces a stream of Events of desired kinds.
    """
    wanted = set(kinds)
    for e in events:
        if e.kind in wanted:
            yield e


def rolling_spend(events: Iterable[Event]) -> Iterator[tuple[int, int]]:
    """
    For each event, yield (ts, cumulative_purchase_cents).
    Demonstrates maintaining state in a generator.
    """
    total = 0
    for e in events:
        if e.kind == "purchase":
            total += e.amount_cents
        yield (e.ts, total)


# ----------------------------
# 4) itertools essentials: chain, islice, pairwise, batched
# ----------------------------


def itertools_examples() -> None:
    a = [1, 2, 3]
    b = (x * 10 for x in range(4))  # Generator

    # chain: treat multiple iterables as one stream
    # chain -> [1, 2, 3, 0, 10, 20, 30]
    combined = chain(a, b)
    print("chain ->", list(combined))

    # islice: take a window from a stream (works on any iterator)
    first_five = list(islice(make_events(10_000_000), 5))
    print("islice(events, 5) ->", first_five)

    # pairwise: consecutive pairs (3.10+)
    # Useful for deltas: (t0,t1), (t1,t2), ...
    times = [10, 14, 21, 23]
    deltas = [b - a for a, b in pairwise(times)]
    print("pairwise deltas ->", deltas)

    # batched: Python 3.12+ has itertools.batched
    # In 3.11, use a tiny helper (below).
    for batch in batched_311(range(10), 4):
        print("batch:", batch)


def batched_311(iterable: Iterable[int], n: int) -> Iterator[tuple[int, ...]]:
    """
    3.11-compatible batched(). Produces tuples of size n (last may be shorter).
    """
    if n <= 0:
        raise ValueError("n must be > 0")
    it = iter(iterable)
    while True:
        chunk = tuple(islice(it, n))
        if not chunk:
            return
        yield chunk


# ----------------------------
# 5) The main exercise: rewrite "load then process" into streaming
# ----------------------------


def load_everything_then_process(n: int) -> int:
    return stream_and_process(n)
    """
    Anti-pattern (for large n):
    1) materialize all events
    2) materialize filtered list
    3) sum
    """
    # events = list(make_events(n))
    # purchases = [e.amount_cents for e in events if e.kind == "purchase"]
    # return sum(purchases)


def stream_and_process(n: int) -> int:
    """
    Streaming pattern:
    - never holds all events in memory
    - never holds all purchases in memory
    """
    return sum(e.amount_cents for e in make_events(n) if e.kind == "purchase")


def main() -> None:
    events_small = list(make_events(50))
    comprehension_examples(events_small)

    totals = too_complex_as_comprehension(events_small)
    print("purchase totals per user:", dict(sorted(totals.items())))

    spend = streaming_pipeline(events_small)
    print("streaming_pipeline purchase sum:", spend)

    print(
        "only_kinds(view, purchase) first 5:",
        list(islice(only_kinds(events_small, "view", "purchase"), 5)),
    )

    print("rolling_spend first 5:", list(islice(rolling_spend(events_small), 5)))

    itertools_examples()

    # Sanity check: both approaches match
    n = 1000
    a = load_everything_then_process(n)
    b = stream_and_process(n)
    print("same result?", a == b, a, b)


if __name__ == "__main__":
    main()
