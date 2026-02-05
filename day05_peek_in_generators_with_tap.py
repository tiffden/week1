import random
from collections.abc import Callable, Iterable, Iterator
from itertools import tee

# ----------------------------
# TypeVar declares a generic type. “whatever type goes in, the same type comes out”
# So tap can work with int, str, Event, etc., and keep type checking consistent.
# pre 3.12 syntax:
#   from typing import TypeVar
#   T = TypeVar("T")
#   def peekable(it: Iterable[T]) -> tuple[T, Iterator[T]]:
# post 3.12 syntax: [T] is now built-in syntax for generics, no need to import TypeVar
# ----------------------------


# Run the passed in function on the item, then yield the item unchanged
# think of tap(...) as wrapping the iterator with a side‑effect function,
# generator functions don’t execute when you call them; only when you iterate them.
# Python does not run the for x in it: loop with x = tap(...)
# Instead, it:
# 	1.	Creates a generator object
# 	2.	Returns it immediately
# 	3.	Stores the function’s state (including it and fn) to run later
#
# Generators are pulled, not pushed.
#   •	The consumer calls next() repeatedly (directly or via for)
#   •	The generator runs until it hits yield
#   •	The generator pauses
#   •	Repeat
def tap[T](it: Iterable[T], fn: Callable[[T], None]) -> Iterator[T]:
    for x in it:
        fn(x)
        yield x


# Method 2 - if you really need to peek ahead without consuming
# peekable is a function that works for any type T.
# It takes an iterable of T, and returns a tuple containing
# one T (the first item) and an iterator of T (the rest)
# this can work on any iterable, including generators
#   peekable([1, 2, 3])    # list (iterable, not iterator)
#   peekable(range(10))    # range (iterable, not iterator)
#   peekable(gen())        # generator (iterator)
# DO NOT USE ON SOCKETS (see notes in day05)
def peekable[T](it: Iterable[T]) -> tuple[T, Iterator[T]]:
    itr = iter(it)  # get the iterator from the iterable
    first = next(itr)  # consumes one

    # iterating g2 will hit yield first, then enter the yield from itr
    def new_iter() -> Iterator[T]:
        yield first  # w/o it, the returned iterator would start at the 2nd element
        yield from itr  # same as:  for x in itr: yield x

    return first, new_iter()


def main() -> None:
    # create a simple generator of random ints
    n = random.randint(5, 10)
    print("divisor n:", n)

    g = (x for x in range(1, 100) if x % n == 0)

    method1, method2 = tee(g)  # split into two independent iterators

    # ----------------------------
    # tap only prints when the iterator is actually consumed
    # so sum(...) will trigger the prints, not these calls
    # ----------------------------

    # Method 1 - tap
    method1 = tap(method1, lambda x: print(f"method1 peek at: {x:>6,}"))

    # Method 2 - peekable
    # method2 is now "owned" by g2, don't use it since g2 will pull from it
    first, g2 = peekable(method2)  # g2 still yields the first item again

    print("first is", first)

    # tap on g2 (let's see what we have - the full iterator)
    g2 = tap(g2, lambda x: print(f"g2 peek at: {x:05d}"))  # zero-pad

    total1 = sum(method1)  # consumes the generator, so all items printed
    total2 = sum(g2)  # consumes the generator, so all items printed

    # tap on method2 (exhausted g2 already consumed it)
    method2 = tap(method2, lambda x: print("method2 peek at:", x))
    total3 = sum(method2)  # the generator is already exhausted, so nothing printed

    print("total-method1:", total1)
    print("total-g2:", total2)
    print("total-method2:", total3)

    ten_numbers = range(1, 11)
    count_to_ten = tap(ten_numbers, lambda x: print("ten_numbers peek at:", x))
    total4 = sum(count_to_ten)  # consume to see the taps

    front, full = peekable(ten_numbers)  # range (iterable, not iterator)
    print("front:", front)
    print("rest:", list(full))
    print("total-count_to_ten:", total4)


if __name__ == "__main__":
    main()
