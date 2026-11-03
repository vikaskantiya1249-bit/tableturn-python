"""The floor. A table's state is derived on read from its current seating — `seated` while the party is at
it, `uncleared` once they have left and nobody has wiped it, `free` otherwise. There is no stored state flag."""
