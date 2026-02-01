from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import NewType
from uuid import UUID, uuid4

# Notes
# from __future__ import annotations - use for dataclasses, delays evaluations
# from dataclasses import asdict, dataclass, field - otherwise all instances;
#   asdict/astuple - careful it recurses dataclasses into plain dict/tuples
#   use it only for serialization (& debugging)
# from typing import NewType - static type checking, noruntime overhead

# ----- Value Objects (immutable) -----
UserId = NewType("UserId", UUID)
OrderId = NewType("OrderId", UUID)

# FROZEN - Use for:
# IDs, coordinates, money, timestamps-as-values, “value semantics” objects
# Keys in dicts/sets (immutability helps correctness)
# (lists are still mutable, use tuples)


# SLOTS - is not per instance
# store instance attributes in a FIXED-size array/tuple
# rather than the default per-instance dynamic dictionary (__dict__)
# records, fixed field objects, configuration objects, parsed data chunks, geo coords
@dataclass(frozen=True, slots=True)
class Money:
    """Simple money value object (currency fixed to USD for Day 2)."""

    amount: Decimal

    # Hook for validation, normalization, and safe mutation in a frozen dataclass
    # In a @dataclass, Python auto-generates __init__.
    # __post_init__ automatically called immediately after that generated __init__
    # Return value is ignored → -> None is documentation for readers and type checkers
    def __post_init__(self) -> None:
        if self.amount.is_nan():  # Not a Number
            raise ValueError("Money amount cannot be NaN")
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

        # Normalize to cents
        normalized = self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # What object.__setattr__ does
        # Bypasses the frozen restriction
        # Writes directly to the object
        # ONLY appropriate during initialization, don't ever use setattr elsewhere
        object.__setattr__(self, "amount", normalized)

    def __add__(self, other: Money) -> Money:
        return Money(self.amount + other.amount)

    def __mul__(self, n: int) -> Money:
        if n < 0:
            raise ValueError("Cannot multiply Money by a negative integer")
        return Money(self.amount * n)

    def __sub__(self, other: Money) -> Money:
        result = self.amount - other.amount
        if result < 0:
            raise ValueError("Money subtraction would go negative")
        return Money(result)


@dataclass(frozen=True, slots=True)
class DiscountRate:
    rate: Decimal

    def __post_init__(self) -> None:
        if self.rate.is_nan():  # Not a Number
            raise ValueError("DiscountRate cannot be NaN")
        if not (Decimal("0.00") <= self.rate <= Decimal("1.00")):
            raise ValueError("DiscountRate must be between 0.00 and 1.00")
        normalized = self.rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        object.__setattr__(self, "rate", normalized)

    @property
    def percentage_of_full_price(self) -> Money:
        return Money(Decimal(1.00) - self.rate)

    @property
    def multiplier(self) -> Decimal:
        """Portion of price to pay after discount (e.g. 0.10 off -> 0.90 pay)."""
        return Decimal("1.00") - self.rate

    def apply_to_unit_price(self, unit_price: Money) -> Money:
        """Return discounted unit price."""
        return Money(unit_price.amount * self.multiplier)


# ----- Entities / Aggregates (mutable, but slotted) -----


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


@dataclass(frozen=True, slots=True)
class LineItem:
    sku: str
    unit_price: Money
    quantity: int = 1
    optional_discount: DiscountRate | None = None

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

        discounted_unit = self.optional_discount.apply_to_unit_price(self.unit_price)
        return discounted_unit * self.quantity


@dataclass(slots=True)
class Order:
    id: OrderId
    user_id: UserId
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    items: list[LineItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")

    # --- behavior / invariants ---
    def add_item(self, item: LineItem) -> None:
        # Example validation rule: prevent duplicate SKU by merging quantities.
        for i, existing in enumerate(self.items):
            if existing.sku == item.sku:
                merged = LineItem(
                    sku=existing.sku,
                    unit_price=existing.unit_price,  # assume same price for Day 2
                    quantity=existing.quantity + item.quantity,
                    optional_discount=existing.optional_discount,
                )
                self.items[i] = merged
                return
        self.items.append(item)

    @property
    def total_items(self) -> int:
        return sum(li.quantity for li in self.items)

    @property
    def total_cost(self) -> Money:
        total = Money(Decimal("0"))
        for li in self.items:
            total = total + li.subtotal_after_discount
        return total

    @property
    def total_discount_applied(self) -> Money:
        before = Money(Decimal("0"))
        after = Money(Decimal("0"))
        for li in self.items:
            before = before + li.subtotal
            after = after + li.subtotal_after_discount
        return before - after

    def to_dict(self) -> dict:
        """Explicit serialization boundary (prefer over asdict() everywhere)."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "created_at": self.created_at.isoformat(),
            "items": [
                {
                    "sku": li.sku,
                    "unit_price": str(li.unit_price.amount),
                    "quantity": li.quantity,
                    "subtotal": str(li.subtotal.amount),
                    "discount rate": (
                        str(li.optional_discount.rate) if li.optional_discount else None
                    ),
                }
                for li in self.items
            ],
            "total_cost": str(self.total_cost.amount),
        }


# ----- quick demo -----


def demo() -> None:
    user = User(id=UserId(uuid4()), email="tee@example.com")
    order = Order(id=OrderId(uuid4()), user_id=user.id)

    order.add_item(
        LineItem(
            sku="COFFEE",
            unit_price=Money(Decimal("10.00")),
            quantity=1,
            optional_discount=DiscountRate(Decimal("0.10")),
        )
    )
    order.add_item(LineItem(sku="MUG", unit_price=Money(Decimal("7.25")), quantity=2))
    order.add_item(LineItem(sku="MUG", unit_price=Money(Decimal("7.25")), quantity=1))

    print(user, "\n")
    print("Total Items: ", order.total_items)  # 4
    print(order.total_cost, "\n")  # Money(amount=Decimal('34.25'))
    print("Dict:", order.to_dict(), "\n")

    # asdict is OK for quick debugging, but it will recurse and keep Decimals etc.
    # snapshot =
    print("Snapshot: ", asdict(order))


if __name__ == "__main__":
    print("********** START *************")
    demo()
    print("========== END  ==============")
