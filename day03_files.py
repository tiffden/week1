from __future__ import annotations

import textwrap
from collections.abc import Iterable, Iterator, Mapping, MutableSequence, Sequence
from dataclasses import dataclass, field  # asdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

# , SupportsInt, SupportsFloat, Any
from typing import NewType, Protocol, TypedDict, overload
from uuid import UUID, uuid4

# Notes
# Store data in concrete containers (list)
# Expose / accept data via interfaces (Sequence)
# _orders should remain a list[Order]
# The class itself should present as a Sequence[Order]
# You do not want _orders: Sequence[Order] if you intend to mutate it.
# Mapping - computes total by looking up unit prices from a mapping not LineItem’s $$

# ----- Value Objects (immutable) -----
UserId = NewType("UserId", UUID)
OrderId = NewType("OrderId", UUID)
Number = int | Decimal


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "USD"

    @classmethod
    def zero(cls, currency: str = "USD") -> Money:
        return cls(Decimal("0.00"), currency)

    def __post_init__(self) -> None:
        if self.amount.is_nan():  # Not a Number
            raise ValueError("Money amount cannot be NaN")
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

        # Normalize to cents
        normalized = self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        object.__setattr__(self, "amount", normalized)

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return Money(self.amount + other.amount, self.currency)

    def __mul__(self, n: Number) -> Money:
        if isinstance(n, (int, Decimal)):
            return Money(self.amount * Decimal(n), self.currency)
        # else returns NotImplemented (which triggers __rmul__)

    # 1.	Call a.__mul__(b)
    # 2.	If that returns NotImplemented, try b.__rmul__(a)
    # 3.	If neither works → TypeError
    def __rmul__(self, n: Number) -> Money:
        # Enables: int/Decimal * money; mul expects money, int/Decimal
        return self.__mul__(n)

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"

    def __sub__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        result = self.amount - other.amount
        if result < 0:
            raise ValueError("Money subtraction would go negative")
        return Money(result, self.currency)


@dataclass(frozen=True, slots=True)
class Percent:
    value: Decimal  # stored as 0–1

    def __post_init__(self) -> None:
        if not (Decimal("0") <= self.value <= Decimal("1")):
            raise ValueError("Percent must be between 0 and 1")

    def of(self, m: Money) -> Money:
        return Money(m.amount * self.value, m.currency)


class Priced(Protocol):
    unit_price: Money


# FREE FUNCTION
def sum_prices(things: Sequence[Priced]) -> Money:
    if not things:
        return Money.zero()
    currency = things[0].unit_price.currency
    for t in things:
        if t.unit_price.currency != currency:
            raise ValueError("Mixed currencies in sum_prices")

    return sum((t.unit_price for t in things), start=Money.zero(currency))


# FREE FUNCTION
def price_total_from_table(
    items: Sequence[LineItem],
    prices: Mapping[str, Money],
) -> Money:
    """
    Compute total cost from a read-only SKU->Money price table.
    Raises KeyError if a SKU is missing or currencies mismatch in Money.__add__.
    """
    if not items:
        return Money.zero()

    # Derive currency from the first price we encounter
    # This assumes single-currency pricing.
    # You could also require a currency arg explicitly.
    first_sku = items[0].sku
    if first_sku not in prices:
        raise KeyError(f"Missing price for SKU {first_sku!r}")

    total = Money.zero(prices[first_sku].currency)

    for li in items:
        unit = prices.get(li.sku)
        if unit is None:
            raise KeyError(f"Missing price for SKU {li.sku!r}")
        total = total + (unit * li.quantity)

    return total


# ----- Entities / Aggregates (mutable, but slotted) -----


class LineItemDict(TypedDict):
    sku: str
    unit_price: str
    quantity: int
    subtotal: str
    discount_rate: str | None


class OrderDict(TypedDict):
    id: str
    user: str
    created_at: str
    order_status: str
    items: list[LineItemDict]
    total_cost: str


@dataclass(slots=True)
class User:
    id: UserId
    email: str
    display_name: str = ""

    def __post_init__(self) -> None:
        if "@" not in self.email or self.email.count("@") != 1:
            raise ValueError(f"Invalid email: {self.email!r}")
        if not self.display_name:
            # default display name from email prefix
            self.display_name = self.email.split("@", 1)[0]


@dataclass(slots=True)
class Order:
    id: OrderId
    user: User
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # self._items is the private, mutable storage
    # items_view is the public, read-only interface

    _items: list[LineItem] = field(default_factory=list)

    order_status: str = "new"

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")

    # Note the lack of commas (if commas it turns into a tuple)
    def __str__(self) -> str:
        s = (
            f"Order {self.id} for {self.user.email} "
            f"with {len(self._items)} items "
            f"[status={self.order_status}]"
        )
        return s

    @property
    def items_view(self) -> tuple[LineItem, ...]:
        """Return an immutable view of the order's items."""
        return tuple(self._items)

    @property
    def total_items(self) -> int:
        return sum(li.quantity for li in self._items)

    @property
    def total_cost(self) -> Money:
        total = Money(Decimal("0"))
        for li in self._items:
            total = total + li.subtotal_after_discount
        return total

    @property
    def total_discount_applied(self) -> Money:
        before = Money(Decimal("0"))
        after = Money(Decimal("0"))
        for li in self._items:
            before = before + li.subtotal
            after = after + li.subtotal_after_discount
        return before - after

    # --- behavior / invariants ---
    def add_item(self, item: LineItem) -> None:
        # Example validation rule: prevent duplicate SKU by merging quantities.
        for i, existing in enumerate(self._items):
            if existing.sku == item.sku:
                merged = LineItem(
                    sku=existing.sku,
                    unit_price=existing.unit_price,  # assume same price for Day 2
                    quantity=existing.quantity + item.quantity,
                    optional_discount=existing.optional_discount,
                )
                self._items[i] = merged
                return
        self._items.append(item)

    def submit(self) -> None:
        if self.order_status != "new":
            raise ValueError("Only NEW orders can be submitted")
        self.order_status = "SUBMITTED"
        print(f"Order Status: {self.order_status} {self.id=}")

    def mark_paid(self) -> None:
        if self.order_status != "SUBMITTED":
            raise ValueError("Only SUBMITTED orders can be paid")
        self.order_status = "PAID"
        print(f"Order Status: {self.order_status} {self.id=}")

    def print_order(self) -> None:
        def fmt_money(m: Money) -> str:
            # Keep it simple: dollars.cents with 2 decimals
            return f"{m.amount:.2f}"

        print(
            f"Order {self.id}  "
            f"Status={self.order_status}  "
            f"Created={self.created_at.isoformat()}"
        )
        print(f"Customer: {self.user.email}")
        print("-")

        # Column widths (tune as desired)
        w_idx = 3
        w_sku = 28
        w_unit = 10
        w_qty = 5
        w_sub = 12
        w_disc = 7

        header = (
            f"{'#':>{w_idx}}  "
            f"{'SKU':<{w_sku}}  "
            f"{'Unit':>{w_unit}}  "
            f"{'Qty':>{w_qty}}  "
            f"{'Subtotal':>{w_sub}}  "
            f"{'Disc':>{w_disc}}"
        )
        print(header)
        print("-" * len(header))

        for i, li in enumerate(self._items, start=1):
            sku_lines = textwrap.wrap(li.sku, width=w_sku) or [""]
            unit_s = fmt_money(li.unit_price)
            sub_s = fmt_money(li.subtotal_after_discount)
            disc_s = (
                f"{int(li.optional_discount.value * 100):>2}%"
                if li.optional_discount
                else "-"
            )
            # First line with numbers
            print(
                f"{i:>{w_idx}}  "
                f"{sku_lines[0]:<{w_sku}}  "
                f"{unit_s:>{w_unit}}  "
                f"{li.quantity:>{w_qty}}  "
                f"{sub_s:>{w_sub}}  "
                f"{disc_s:>{w_disc}}"
            )

            # Continuation lines for wrapped SKU
            for cont in sku_lines[1:]:
                print(f"{'':>{w_idx}}  {cont:<{w_sku}}")

        print("-")
        print(f"Items: {self.total_items}")
        print(f"Total: {fmt_money(self.total_cost)}")
        print(f"Discount applied: {fmt_money(self.total_discount_applied)}")
        print("")


# FREE METHOD
def to_dict(self) -> OrderDict:
    return {
        "id": str(self.id),
        "user": self.user.email,
        "created_at": self.created_at.isoformat(),
        "order_status": self.order_status,
        "items": [
            {
                "sku": li.sku,
                "unit_price": str(li.unit_price.amount),
                "quantity": li.quantity,
                "subtotal": str(li.subtotal.amount),
                "discount_rate": (
                    str(li.optional_discount.value) if li.optional_discount else None
                ),
            }
            for li in self._items
        ],
        "total_cost": str(self.total_cost.amount),
    }


@dataclass(frozen=True, slots=True)
class LineItem:
    sku: str
    unit_price: Money
    quantity: int = 1
    optional_discount: Percent | None = None

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise ValueError("sku must be non-empty")
        if self.quantity <= 0:
            raise ValueError("quantity must be >= 1")

    @property
    def subtotal(self) -> Money:
        return self.unit_price * self.quantity

    @property
    def subtotal_after_discount(self) -> Money:
        if self.optional_discount is None:
            return self.subtotal
        return self.subtotal - self.optional_discount.of(self.subtotal)


# MUTABLESEQUENCE
@dataclass(slots=True)
class LineItems(MutableSequence[LineItem]):
    _items: list[LineItem] = field(default_factory=list)

    def __init__(self, items: Iterator[LineItem] | None = None) -> None:
        # Normalize to a real list
        self._items = list(items) if items is not None else []

    @overload
    def __getitem__(self, index: int) -> LineItem: ...
    @overload
    def __getitem__(self, index: slice) -> LineItems: ...

    def __getitem__(self, index: int | slice) -> LineItem | LineItems:
        if isinstance(index, slice):
            return LineItems(iter(self._items[index]))
        return self._items[index]

    @overload
    def __setitem__(self, index: int, value: LineItem) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterator[LineItem]) -> None: ...

    def __setitem__(
        self, index: int | slice, value: LineItem | Iterator[LineItem]
    ) -> None:
        if isinstance(index, slice):
            if isinstance(value, (str, bytes)) or not isinstance(value, Iterator):
                raise TypeError("Expected an Iterator of LineItem for slice assignment")
            self._items[index] = list(value)
        else:
            if not isinstance(value, LineItem):
                raise TypeError("Expected a LineItem for single item assignment")
            self._items[index] = value

    def __delitem__(self, index: int | slice) -> None:
        del self._items[index]

    def insert(self, index: int, value: LineItem) -> None:
        if not isinstance(value, LineItem):
            raise TypeError("Expected a LineItem for insert()")
        self._items.insert(index, value)

    def __len__(self) -> int:
        return len(self._items)


# SEQUENCE
# Inherit from Sequence[Order]
# Keep _orders as a list[Order]
# Sequence is a read-only, ordered container interface.
# When you make Orders(Sequence[Order]), you are making a promise to callers
# and to the type checker:
# “You can treat Orders like an indexable, sliceable, length-known,
# iterable collection of Orders — but you cannot assume mutation operations exist.”


# A Sequence[T] guarantees:
# 	•	len(seq) works
# 	•	seq[i] works (integer indexing)
# 	•	seq[i:j:k] works (slicing)
# 	•	for x in seq: works (iteration)
# 	•	x in seq works (membership test)
# 	•	seq.index(x) works
# 	•	seq.count(x) works
# 	•	reversed(seq) works
# It does not guarantee:
# 	•	append, extend, insert, remove, pop, clear, sort, etc.
# That’s MutableSequence.
@dataclass(slots=True)
class Orders(Sequence[Order]):
    _orders: list[Order] = field(default_factory=list)

    @overload
    def __getitem__(self, index: int) -> Order: ...
    @overload
    def __getitem__(self, index: slice) -> Orders: ...

    def __getitem__(self, index: int | slice) -> Order | Orders:
        if isinstance(index, slice):
            return Orders(list(self._orders[index]))
        return self._orders[index]

    # To be a proper Sequence, you must implement:
    # 	1.	__len__(self) -> int
    # 	2.	__getitem__(self, index: int | slice) -> ...
    def __len__(self) -> int:
        return len(self._orders)

    # if __getitem__ slicing logic, filtering, defensive copying, domain validation, etc
    # you want to write __iter__ for efficiency, because it repeatedly calls __getitem__
    def __iter__(self) -> Iterator[Order]:
        return iter(self._orders)

    # --- behavior / invariants ---
    def add_order(self, order: Order) -> None:
        self._orders.append(order)

    def for_user(self, user_id: UserId) -> Orders:
        user_orders = Orders()
        for order in self._orders:
            if order.user.id == user_id:
                user_orders.add_order(order)
        return user_orders

    def view(self) -> tuple[Order, ...]:
        return tuple(self._orders)


# FREE FUNCTION -- Iterable is most generic
# Now it accepts: Sequence, Iterator, Generator, Orders
def print_orders(orders: Iterable[Order]) -> None:
    print("============ ORDERS ====================")
    for o in orders:
        o.print_order()
    print("========== END OF ORDERS  ==============")


# FREE FUNCTION
def make_line_item(
    *,
    sku: str,
    prices: Mapping[str, Money],
    quantity: int = 1,
    discount: Percent | None = None,
) -> LineItem:
    try:
        unit_price = prices[sku]
    except KeyError as exc:
        raise KeyError(f"Unknown SKU {sku!r}") from exc

    return LineItem(
        sku=sku,
        unit_price=unit_price,
        quantity=quantity,
        optional_discount=discount,
    )


# FREE FUNCTION
def maybe_find_line_item(
    items: Sequence[LineItem],
    sku: str,
) -> LineItem | None:
    for item in items:
        if item.sku == sku:
            return item
    return None


# FREE FUNCTION
def iter_all_line_items(orders: Sequence[Order]) -> Iterator[LineItem]:
    """Yield all line items from a sequence of orders."""
    for order in orders:
        yield from order.items_view


# ----- quick demo -----
# This has a variety of ways of filling LineItem, one uses direct, another
# uses a price table mapping.


def demo() -> None:
    master_orders = Orders()

    # container - read-only mapping of SKU to Money price
    # TypedDict - dict with fixed keys - used for to_dict()
    price_table: dict[str, Money] = {
        "COFFEE": Money(Decimal("10.00")),
        "MUG": Money(Decimal("7.25")),
        "COOKIE": Money(Decimal("3.00")),
        "BAGEL": Money(Decimal("1.00")),
        "TEA": Money(Decimal("5.50")),
        "HAT": Money(Decimal("15.00")),
        "TSHIRT": Money(Decimal("12.00")),
    }

    user1 = User(id=UserId(uuid4()), email="tee@example.com")
    order1 = Order(id=OrderId(uuid4()), user=user1)
    # Without the trailing comma, your diff changes two lines instead of one:
    lineA = make_line_item(
        sku="COFFEE",
        prices=price_table,
        quantity=1,
        discount=Percent(Decimal("0.10")),
    )
    order1.add_item(lineA)
    order1.add_item(make_line_item(sku="MUG", prices=price_table, quantity=2))
    order1.add_item(make_line_item(sku="MUG", prices=price_table, quantity=1))  # merges
    order1.submit()
    order1.mark_paid()
    master_orders.add_order(order1)

    user2 = User(id=UserId(uuid4()), email="dee@thesecond.com")
    order2 = Order(id=OrderId(uuid4()), user=user2)
    order2.add_item(
        LineItem(
            sku="BAGEL",
            unit_price=Money(Decimal("3.00")),
            quantity=3,
            optional_discount=Percent(Decimal("0.50")),
        )
    )
    master_orders.add_order(order2)

    order3 = Order(id=OrderId(uuid4()), user=user2)
    order3.add_item(LineItem(sku="HAT", unit_price=Money(Decimal("15.00")), quantity=1))
    master_orders.add_order(order3)

    print_orders(master_orders)
    print_orders(master_orders.for_user(user2.id))

    print(order1)  # __str__()
    ten_dollars = Money(Decimal("10.005"))  # tests rounding
    print("Rounding example: ", ten_dollars)  # __str__()
    print("")

    total = price_total_from_table(order1.items_view, price_table)
    print(f"Total from price table for order1: {total}")

    for o in master_orders:
        print("TypedDict:", to_dict(o))


if __name__ == "__main__":
    print("****************--- Demo of Orders system ---****************")
    demo()
