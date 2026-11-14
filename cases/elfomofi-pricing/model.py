"""Recovered data layouts and exact-input ladder arithmetic.
The ladder constructor and the complete engine are NOT reconstructed here.
Python names are analyst labels, not recovered original source identifiers.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PostedPrice:
    mantissa: int
    adjustment: int


def decode_prices(word: int):
    """Slot 2: uint32 timestamp + eight 28-bit lanes (22-bit price, signed 6-bit tilt)."""
    if not 0 <= word < 1 << 256:
        raise ValueError("Expected uint256")
    prices = []
    for i in range(8):
        lane = (word >> (32 + 28 * i)) & ((1 << 28) - 1)
        signed = lane >> 22
        prices.append(
            PostedPrice(lane & ((1 << 22) - 1), signed - 64 if signed >= 32 else signed)
        )
    return word & ((1 << 32) - 1), prices


def decode_metadata(words):
    """13 uint256 words returned by getMetadata(address), decoded from three slots.
    Names for the first four fields are resolved by use; remaining policy fields
    are retained as raw values except the observed base-lot size and reference.
    """
    config, reference, aux = words
    fields = [
        (config >> offset) & ((1 << width) - 1)
        for offset, width in [
            (0, 8),
            (8, 8),
            (16, 8),
            (24, 8),
            (32, 8),
            (40, 16),
            (56, 8),
            (64, 128),
            (192, 16),
            (208, 16),
            (224, 8),
        ]
    ]
    return tuple(fields + [reference & ((1 << 160) - 1), aux])


def exact_input(levels, amount, *, buy_base=False, base_decimals=18, quote_decimals=6):
    """Consume (base capacity, quote/base price scaled by 1e12) levels.
    Sell: floor output separately at each consumed level. Buy: ceil cost of a
    complete level, then floor base output at the final partially consumed level.
    Tested for amounts inside the captured ladder; unfilled requests raise.
    Caller/age/inventory adjustments must already be in the supplied prices.
    Same-block post-traversal penalties are outside this function's scope.
    """
    if amount < 0:
        raise ValueError("Expected unsigned amount")
    scale = 10 ** (base_decimals + 12 - quote_decimals)
    remaining = amount
    out = 0
    for capacity, price in levels:
        if capacity < 0 or price <= 0:
            raise ValueError("Invalid level")
        if buy_base:
            cost = (capacity * price + scale - 1) // scale
            if remaining >= cost:
                out += capacity
                remaining -= cost
            else:
                out += remaining * scale // price
                remaining = 0
        else:
            used = min(remaining, capacity)
            out += used * price // scale
            remaining -= used
        if not remaining:
            return out
    if remaining:
        raise ValueError("Input exceeds captured ladder")
    return out
