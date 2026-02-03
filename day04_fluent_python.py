from __future__ import annotations

import collections
from random import choice

# --- Fluent Python (pgs. 5-35) ----------------------------
# FrenchDeck Examples - sorted, iteration, slicing, indexing
# listcomp - list comprehensions
# genexp - generator expressions
# namedtuple
# unpacking
Card = collections.namedtuple("Card", ["rank", "suit"])


class FrenchDeck:
    # Ranks: ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    # listcomp version:
    ranks = [str(n) for n in range(2, 11)] + list("JQKA")

    # dict '2': 1, '3': 2, ..., 'A': 13}
    # listcomp version with enumerate:
    rank_values = {rank: idx for idx, rank in enumerate(ranks, start=0)}

    # suits = "spades hearts diamonds clubs".split(), or use a dict:
    suit_values = dict(spades=3, hearts=2, diamonds=1, clubs=0)

    # formatted = ", ".join([f"Ind-{i}:'{rank}'" for i, rank in enumerate(ranks)])
    # print("Ranks:", f"[{formatted}]")
    print("Ranks:", rank_values)
    print("Suits:", suit_values)

    def __init__(self):
        # self._cards = [Card(rank, suit) for suit in self.suits for rank in self.ranks]
        # listcomp version:
        self._cards = [
            Card(rank, suit) for suit in self.suit_values for rank in self.ranks
        ]
        # print with generator expression:
        for i, c in enumerate(
            (f"{r:>2} of {s}" for r in self.ranks for s in self.suit_values), start=1
        ):
            print(f"{i:>2} - Card: {c}")

    def __len__(self):
        return len(self._cards)

    def __iter__(self):
        return iter(self._cards)

    def __getitem__(self, position):
        return self._cards[position]  # enables indexing & slicing [_cards is a list]


# Sorting by rank then suit
def spades_high_sort_key(card: Card) -> int:
    return (
        FrenchDeck.suit_values[card.suit] * len(FrenchDeck.ranks)
        + FrenchDeck.rank_values[card.rank]
    )


# Sorting by suit then rank
def spades_high_sort_key2(card: Card) -> int:
    rank_index = FrenchDeck.rank_values[card.rank]  # 0..12
    max_suit = max(FrenchDeck.suit_values.values())  # 3
    suit_index = max_suit - FrenchDeck.suit_values[card.suit]  # spades -> 0, clubs -> 3
    return rank_index * len(FrenchDeck.suit_values) + suit_index


def FrenchDeck_pg8() -> None: ...


# --- Demo -------------------------------------------------------------------


def main_fluent_python() -> None:
    deck = FrenchDeck()

    beer_card = Card("7", "diamonds")
    nbr, shape = beer_card  # unpacking
    print("Beer Card UNPACKED:", beer_card, "Nbr:", nbr, "Shape:", shape)
    print("Beer Card:", beer_card, (beer_card in deck))
    print("Deck Length:", len(deck))

    # -1 indexing prints the last card
    print(
        "First:", deck[0], "Last:", deck[-1]
    )  # use commas, auto spaces, else f-string
    # for i in range(2, 5):  # the other method to get slices
    for _ in range(3):  # the _ is a throwaway variable
        print("Random Pick:", choice(deck))
    # Slicing
    print("Slice 0-2:", deck[:3])  # or deck[0:3]
    print("Slice 12-15:", deck[12:16])
    print("Slice every 13th card:", deck[::13])
    # Iteration
    for card in deck[2:6]:
        print("Forward:", card)
    for card in reversed(deck[-3:]):
        print("Reverse:", card)
    # Ellipsis (can't use as slice which is integer or None)
    # Ellipsis is strongest in NumPy for multi-dimensional arrays
    # Can be used as a placeholder in code:
    # todo = ["alpha", ..., "omega"]
    # for item in todo:
    # if item is ...:
    #     print("Ellipsis placeholder found")
    # else:
    #     print("Item:", item)
    print("Ellipsis slice:", ...)  # same as deck[::1]
    # Sorting by rank and suit
    # sorted(iterable, key=some_function) - no parentheses on function!
    # sorted(deck, key=lambda c: fluent_python_pg5_FrenchDeck_sort_key(c))
    for card in sorted(deck, key=spades_high_sort_key):
        print("Sorted:", card)

    for card in sorted(deck, key=spades_high_sort_key2):
        print("Sorted Grouped:", card)

    # string demo - !r uses repr(), !s uses str()
    s = "hi\nthere"
    print(f"{s}")  # uses str -> hi
    #             there
    print(f"{s!r}")  # uses repr -> 'hi\nthere'


if __name__ == "__main__":
    print("*********** Fluent Python Demo *************")
    main_fluent_python()
