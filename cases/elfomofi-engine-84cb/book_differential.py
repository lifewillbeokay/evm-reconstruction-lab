import copy, json, itertools
from eth_abi import encode
from eth_utils import keccak
from price_differential import p, mw, evaluate, responder, RUNTIME, probe


def scenarios():
    out = []
    m = copy.deepcopy(p.ARGS[5][0])
    m[1] = 6
    m[7] = 10
    m[8] = 15
    m[9] = 3
    word = (
        3 | ((2 | (3 << 16)) << 8) | ((5 | (7 << 16)) << 40) | ((10 | (12 << 16)) << 72)
    )
    slot = hex(int.from_bytes(keccak(bytes(64)), "big"))
    for flag, balance, quote_balance, spread in itertools.product(
        [0, 1],
        [0, 1, 10, 11, 29, 30, 31, 100, 119, 120, 139, 140, 149, 150, 200],
        [0, 1, 5, 25, 10000],
        [0, 5, 50000, 100000],
    ):
        for ask in [False, True]:
            if ask and quote_balance != 10000:
                continue
            kwargs = {
                "code": {
                    p.ARGS[4][0]: responder(
                        {"70a08231": encode(["uint256"], [balance])}
                    ),
                    p.ARGS[2]: responder(
                        {"70a08231": encode(["uint256"], [quote_balance])}
                    ),
                },
                "overrides": {p.ENGINE: {slot: hex(word | (flag << 232))}},
            }
            values = [spread, 10**12, p.ARGS[4][0], m]
            out.append(
                (
                    f"{'ask' if ask else 'bid'}-{flag}-{balance}-{quote_balance}-{spread}",
                    (
                        0x3395 if ask else 0x3101,
                        [spread, 10**12, int(p.ARGS[4][0], 16), 128],
                        mw(m),
                        "asks" if ask else "bids",
                        ["uint256", "uint256", "address", p.META_TYPE],
                        values,
                        "levels",
                    ),
                    kwargs,
                )
            )
    return out
