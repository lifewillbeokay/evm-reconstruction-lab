import copy, json
from eth_abi import encode
from price_differential import p, iv, mw, evaluate, POOL, responder, NOW


def scenarios():
    out = []

    def add(name, *args, **kwargs):
        out.append((name, args, kwargs))

    for decimals in [0, 2, 12, 13]:
        for variant in range(8):
            posted = [123456789123456789, 1234567890, 12, -12]
            ref = [1234567812345678, 123]
            price = 123987123987123987
            if variant == 1:
                posted[0] = 2**256 - 1
            if variant == 2:
                posted[1] = 2**256 - 1
            if variant == 3:
                posted[2] = 1000
            if variant == 4:
                posted[3] = -500
            if variant == 5:
                ref[0] = 2**256 - 1
            if variant == 6:
                ref[1] = 2**256 - 1
            if variant == 7:
                price = 2**256 - 1
            words = {128 + i * 32: v for i, v in enumerate(posted)} | {
                512 + i * 32: v for i, v in enumerate(ref)
            }
            add(
                f"pack-{decimals}-{variant}",
                0x4488,
                [decimals, price, 512, 128],
                words,
                "pack",
                [
                    "uint8",
                    "uint256",
                    "(uint256,uint256)",
                    "(uint256,uint256,uint256,int256)",
                ],
                [decimals, price, ref, posted],
                "scalar",
            )
    mask = (1 << 160) - 1
    transformed = [
        "a995eee4e52e52927f39a6aa9aa25691f6ddaa56",
        "5784974ae9ac7c1f56948528c08fa40dfc10bfbf",
        "179fd775dda7e5ab7f771289c4448380963d5979",
        "7f05033b024c42ea9a7a57519251de92fb5a2a1c",
    ]
    origins = [
        "0x"
        + (
            (
                (int(x, 16) ^ int("c471df69cd11fb228f690b7136037ffffffffffe", 16))
                - int("7301c4cc2c1e69fffe", 16)
            )
            * pow(0xD05, -1, 1 << 160)
            & mask
        )
        .to_bytes(20, "big")
        .hex()
        for x in transformed
    ]
    for origin in origins + [p.DEPLOYER, p.ARGS[0], "0x" + "11" * 20]:
        add(
            "special-" + origin,
            0x1D8A,
            [],
            {},
            "special",
            [],
            [],
            "scalar",
            origin=origin,
        )
    for kind in range(6):
        for age in [0, 2, 8, 120]:
            for posted in [0, 90, 100, 110]:
                for ask in [False, True]:
                    m = copy.deepcopy(p.ARGS[5][0])
                    m[1] = 6
                    m[3] = kind
                    m[4] = 3
                    m[6] = 5
                    m[11] = POOL
                    m[12] = 1
                    responses = {
                        "b80777ea": encode(["uint256"], [NOW - 4]),
                        "c6ddb642": encode(["uint256"] * 3, [100000000, 0, 0]),
                        "b5e4b813": encode(
                            ["uint256"] * 4, [100000000, 0, 0, (NOW - 4) * 1000]
                        ),
                        "3850c7bd": encode(["uint256"], [2**96]),
                        "1e2eaeaf": encode(["uint256"], [2**96]),
                    }
                    code = responder(responses)
                    for adjustment, origin, apply_transient in [
                        (0, p.ARGS[0], False),
                        (-5, p.ARGS[0], True),
                        (5, p.DEPLOYER, True),
                        (0, p.DEPLOYER, False),
                    ]:
                        word = ((posted | ((adjustment & 63) << 22)) << 32) + (
                            NOW - age
                        )
                        entry = (
                            0x2E09 if apply_transient else (0x2C9A if ask else 0x2A93)
                        )
                        args = ([int(ask)] if apply_transient else []) + [
                            128,
                            int(p.ARGS[4][0], 16),
                        ]
                        add(
                            f"base-{kind}-{age}-{posted}-{ask}-{adjustment}-{origin}-{apply_transient}",
                            entry,
                            args,
                            mw(m),
                            "base",
                            [p.META_TYPE, "address", "bool", "bool"],
                            [m, p.ARGS[4][0], ask, apply_transient],
                            [0, 0, 0],
                            code={POOL: code, "0x" + "00" * 20: code},
                            overrides={p.ENGINE: {"0x2": hex(word)}},
                            origin=origin,
                        )
    for age in [0, 2, 4, 8]:
        for raw4, raw6 in [(0, 0), (0, 1), (0, 5), (3, 5)]:
            for posted in [9984, 9990, 9999, 10000, 10001, 10010, 10016]:
                for ask in [False, True]:
                    m = copy.deepcopy(p.ARGS[5][0])
                    m[1] = 8
                    m[3] = 3
                    m[4] = raw4
                    m[6] = raw6
                    m[11] = POOL
                    m[12] = 1
                    code = responder({"3850c7bd": encode(["uint256"], [2**96])})
                    add(
                        f"base-pool-{age}-{raw4}-{raw6}-{posted}-{ask}",
                        0x2C9A if ask else 0x2A93,
                        [128, int(p.ARGS[4][0], 16)],
                        mw(m),
                        "base",
                        [p.META_TYPE, "address", "bool", "bool"],
                        [m, p.ARGS[4][0], ask, False],
                        [0, 0, 0],
                        code={POOL: code},
                        overrides={p.ENGINE: {"0x2": hex((posted << 32) + NOW - age)}},
                    )
    for adj in [-(2**255), -100001, -100000, -1, 0, 1, 100001, 2**255 - 1]:
        for ask in [False, True]:
            m = copy.deepcopy(p.ARGS[5][0])
            m[3] = 0
            key = int(
                "22116470a8a062b874d7fcbbce281f71f1c078a760833f3d2faa65621bd10bef", 16
            )
            add(
                f"transient-{adj}-{ask}",
                0x2E09,
                [int(ask), 128, int(p.ARGS[4][0], 16)],
                mw(m),
                "base",
                [p.META_TYPE, "address", "bool", "bool"],
                [m, p.ARGS[4][0], ask, True],
                [0, 0, 0],
                origin=p.DEPLOYER,
                transient={key: adj},
            )
    return out
