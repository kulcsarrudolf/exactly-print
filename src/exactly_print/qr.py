"""A QR code, encoded by hand.

Byte mode, error correction level M, and the smallest of versions 1 to 3
that holds the text: up to 42 characters, which is more than the one short
link the page prints. Those three versions keep their codewords in a single
block, so the data and its Reed-Solomon check bytes follow one another into
the matrix without the interleaving a larger code would need.

`encode` returns the modules as rows of booleans, the first row at the top
and a true module drawn dark. The quiet zone is not part of them: whatever
draws the code leaves the four modules of paper around it.
"""

from functools import lru_cache

# Data and error-correction codewords per version at level M, all one block.
CAPACITY: dict[int, tuple[int, int]] = {1: (16, 10), 2: (28, 16), 3: (44, 26)}
# The centre of the single alignment pattern; version 1 has none.
ALIGN_CENTRE: dict[int, int] = {2: 18, 3: 22}
# Level M as the two bits the format information carries.
EC_BITS = 0b00
# The generator and the mask of the BCH(15, 5) code the format bits use.
G15 = 0b101_0011_0111
G15_MASK = 0b101_0100_0001_0010
# The 1:1:3:1:1 run of a finder pattern with the light modules beside it.
FINDER_RUN = [True, False, True, True, True, False, True, False, False, False, False]
QUIET = 4

MASKS = [
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


def _tables() -> tuple[list[int], list[int]]:
    """Powers of 2 and their logarithms in GF(256), the field the
    Reed-Solomon check bytes are computed in."""
    exp, log, x = [0] * 512, [0] * 256, 1
    for i in range(255):
        exp[i], log[x] = x, i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


EXP, LOG = _tables()


def _mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


def _generator(degree: int) -> list[int]:
    """(x - a^0)(x - a^1)... , the polynomial the data is divided by."""
    poly = [1]
    for i in range(degree):
        shifted = poly + [0]
        for j, c in enumerate(poly):
            shifted[j + 1] ^= _mul(c, EXP[i])
        poly = shifted
    return poly


def _check_bytes(data: list[int], count: int) -> list[int]:
    poly = _generator(count)
    rest = data + [0] * count
    for i in range(len(data)):
        factor = rest[i]
        if factor:
            for j, c in enumerate(poly):
                rest[i + j] ^= _mul(c, factor)
    return rest[len(data) :]


def _codewords(text: str) -> tuple[int, list[int]]:
    """The version that holds the text, and its data and check bytes."""
    raw = text.encode("utf-8")
    # The mode and the length take twelve bits, so the text costs two
    # codewords more than its length.
    version = next((v for v, (data, _) in CAPACITY.items() if len(raw) + 2 <= data), None)
    if version is None:
        raise ValueError(f"{len(raw)} bytes is more than a version 3 QR code holds.")
    data_cw, ec_cw = CAPACITY[version]

    bits: list[int] = []

    def put(value: int, width: int) -> None:
        bits.extend((value >> i) & 1 for i in range(width - 1, -1, -1))

    put(0b0100, 4)  # byte mode
    put(len(raw), 8)
    for byte in raw:
        put(byte, 8)
    put(0, min(4, data_cw * 8 - len(bits)))  # the terminator, as much as fits
    bits.extend([0] * (-len(bits) % 8))

    words = [int("".join(map(str, bits[i : i + 8])), 2) for i in range(0, len(bits), 8)]
    # The two pad bytes the standard names, alternating to the end.
    words += [0xEC if i % 2 == 0 else 0x11 for i in range(data_cw - len(words))]
    return version, words + _check_bytes(words, ec_cw)


def _patterns(version: int) -> tuple[list[list[bool]], list[list[bool]]]:
    """The finders, timing and alignment patterns, and a mask of every
    module the data must step over — the format information included."""
    size = 17 + 4 * version
    modules = [[False] * size for _ in range(size)]
    fixed = [[False] * size for _ in range(size)]

    def put(r: int, c: int, dark: bool) -> None:
        modules[r][c] = dark
        fixed[r][c] = True

    for row, col in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(-1, 8):
            for c in range(-1, 8):
                if 0 <= row + r < size and 0 <= col + c < size:
                    inside = 0 <= r <= 6 and 0 <= c <= 6
                    ring = r in (0, 6) or c in (0, 6)
                    core = 2 <= r <= 4 and 2 <= c <= 4
                    put(row + r, col + c, inside and (ring or core))

    centre = ALIGN_CENTRE.get(version)
    if centre is not None:
        for r in range(-2, 3):
            for c in range(-2, 3):
                put(centre + r, centre + c, max(abs(r), abs(c)) != 1)

    for i in range(8, size - 8):
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)

    for i in (*range(6), 7, 8):
        put(8, i, False)
        put(i, 8, False)
    for i in range(size - 8, size):
        put(8, i, False)
    for i in range(size - 7, size):
        put(i, 8, False)
    put(size - 8, 8, True)  # the one module that is always dark

    return modules, fixed


def _place(modules: list[list[bool]], fixed: list[list[bool]], words: list[int]) -> None:
    """The codewords up and down the symbol, two columns at a time from the
    bottom right corner, stepping over the patterns already there."""
    size = len(modules)
    bits = iter([(w >> i) & 1 for w in words for i in range(7, -1, -1)])
    row, step = size - 1, -1
    for right in range(size - 1, 0, -2):
        if right <= 6:
            right -= 1  # column 6 is the timing pattern, never data
        while True:
            for col in (right, right - 1):
                if not fixed[row][col]:
                    modules[row][col] = bool(next(bits, 0))
            row += step
            if not 0 <= row < size:
                row -= step
                step = -step
                break


def _format_bits(mask: int) -> int:
    data = (EC_BITS << 3) | mask
    rest = data << 10
    for i in range(4, -1, -1):
        if rest >> (10 + i) & 1:
            rest ^= G15 << i
    return ((data << 10) | rest) ^ G15_MASK


def _put_format(modules: list[list[bool]], mask: int) -> None:
    """The fifteen format bits, twice: once around the top left finder and
    once split between the other two, so either copy can be read alone."""
    size = len(modules)
    bits = _format_bits(mask)
    for i in range(15):
        dark = bool((bits >> i) & 1)
        modules[i if i < 6 else i + 1 if i < 8 else size - 15 + i][8] = dark
        modules[8][size - 1 - i if i < 8 else 7 if i == 8 else 14 - i] = dark


def _penalty(modules: list[list[bool]]) -> int:
    """How badly a masked symbol reads, by the four rules of the standard:
    long runs of one colour, blocks of one colour, anything that looks like
    a finder pattern, and a symbol too dark or too light overall."""
    size = len(modules)
    score = 0
    lines = modules + [list(col) for col in zip(*modules, strict=True)]
    for line in lines:
        run = 1
        for i in range(1, size):
            if line[i] == line[i - 1]:
                run += 1
                continue
            score += run - 2 if run >= 5 else 0
            run = 1
        score += run - 2 if run >= 5 else 0
        for i in range(size - 10):
            if line[i : i + 11] in (FINDER_RUN, FINDER_RUN[::-1]):
                score += 40
    for r in range(size - 1):
        for c in range(size - 1):
            block = (modules[r][c], modules[r][c + 1], modules[r + 1][c], modules[r + 1][c + 1])
            if all(block) or not any(block):
                score += 3
    dark = sum(sum(row) for row in modules) * 100 / size**2
    return score + 10 * int(abs(dark - 50) // 5)


@lru_cache(maxsize=8)
def encode(text: str) -> tuple[tuple[bool, ...], ...]:
    """The text as QR modules, row by row from the top; true is dark."""
    version, words = _codewords(text)
    patterns, fixed = _patterns(version)
    _place(patterns, fixed, words)
    size = len(patterns)

    best = None
    for index, mask in enumerate(MASKS):
        tried = [row[:] for row in patterns]
        for r in range(size):
            for c in range(size):
                if not fixed[r][c] and mask(r, c):
                    tried[r][c] = not tried[r][c]
        _put_format(tried, index)
        score = _penalty(tried)
        if best is None or score < best[0]:
            best = (score, tried)
    return tuple(tuple(row) for row in best[1])
