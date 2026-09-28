import pytest

from exactly_print import seo
from exactly_print.qr import G15_MASK, MASKS, _patterns, encode

# The code the page prints, drawn as it comes out of the encoder. It was
# checked against two other encoders and read back by a scanner, so a change
# here is a change in the printed sheet, not a detail of the implementation.
LINK_CODE = [
    "#######.##..####...##.#######",
    "#.....#.#....#..##..#.#.....#",
    "#.###.#..#..#...#...#.#.###.#",
    "#.###.#.#..#..##.#.#..#.###.#",
    "#.###.#...#.#.#.#####.#.###.#",
    "#.....#...#.##.##.##..#.....#",
    "#######.#.#.#.#.#.#.#.#######",
    "........##.#...####..........",
    "#.##.###.##.##.######.#..#.##",
    "#......##..#####.####.###...#",
    "...#####.##..#..#.#.##..#.##.",
    "##.....#.##.#..#....#.#.....#",
    "###########...#..#.#.....##..",
    "#..###.##.##..##.#.#..#...###",
    "##...#####.###...#.###.#..###",
    "####.....#.#..###....#..#..#.",
    "#.#...#.....#.#...####.###.#.",
    ".#.#.#.#.##...##..#.##.#.###.",
    "#.#..#####...###.....##.#.#..",
    "..##....##.#.#####.###.##.#..",
    ".######.#.##.##..##########..",
    "........#..#....#####...#####",
    "#######.##.##.#.#.###.#.##.#.",
    "#.....#.#...###.#.#.#...##...",
    "#.###.#..###.....##.#####.##.",
    "#.###.#.#...#..##...#...##..#",
    "#.###.#.#.#..#..####...#..#.#",
    "#.....#..#.###.##.###.####.#.",
    "#######.#...#.##..####.....#.",
]


def drawn(text: str) -> list[str]:
    return ["".join("#" if cell else "." for cell in row) for row in encode(text)]


def read_back(text: str) -> tuple[int, str]:
    """The symbol read the way a scanner reads it: the mask taken from the
    format information, the modules unmasked, then the codewords off the
    matrix and the text out of them. Returns the error correction level and
    what the code says."""
    modules = [list(row) for row in encode(text)]
    size = len(modules)
    version = (size - 17) // 4

    bits = 0
    for i in range(15):
        row = i if i < 6 else i + 1 if i < 8 else size - 15 + i
        bits |= modules[row][8] << i
    info = (bits ^ G15_MASK) >> 10
    level, mask = info >> 3, info & 0b111

    _, fixed = _patterns(version)
    for r in range(size):
        for c in range(size):
            if not fixed[r][c] and MASKS[mask](r, c):
                modules[r][c] = not modules[r][c]

    stream: list[int] = []
    row, step = size - 1, -1
    for right in range(size - 1, 0, -2):
        if right <= 6:
            right -= 1
        while True:
            for col in (right, right - 1):
                if not fixed[row][col]:
                    stream.append(int(modules[row][col]))
            row += step
            if not 0 <= row < size:
                row -= step
                step = -step
                break

    def take(width: int) -> int:
        nonlocal stream
        value = int("".join(map(str, stream[:width])), 2)
        stream = stream[width:]
        return value

    assert take(4) == 0b0100, "byte mode"
    length = take(8)
    return level, bytes(take(8) for _ in range(length)).decode("utf-8")


def test_the_version_grows_with_the_text():
    assert len(encode("a")) == 21  # version 1
    assert len(encode("x" * 20)) == 25  # version 2
    assert len(encode("x" * 30)) == 29  # version 3


def test_more_than_a_version_3_holds_is_refused():
    encode("x" * 42)
    with pytest.raises(ValueError, match="version 3"):
        encode("x" * 43)


def test_the_finder_patterns_sit_in_three_corners():
    code = drawn(seo.HOME)
    size = len(code)
    eye = ["#######", "#.....#", "#.###.#", "#.###.#", "#.###.#", "#.....#", "#######"]
    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        assert [row[left : left + 7] for row in code[top : top + 7]] == eye
    # The fourth corner is data, and one module below the top left eye is
    # always dark, whatever the text.
    assert code[size - 8][8] == "#"


def test_the_timing_patterns_run_between_the_finders():
    code = drawn(seo.HOME)
    size = len(code)
    for i in range(8, size - 8):
        assert code[6][i] == ("#" if i % 2 == 0 else ".")
        assert code[i][6] == ("#" if i % 2 == 0 else ".")


def test_the_code_on_the_page_is_the_one_that_was_checked():
    assert drawn(seo.HOME) == LINK_CODE
    assert len(LINK_CODE) == 29  # version 3, the smallest that holds the link


def test_a_scanner_reads_the_text_back_out():
    for text in (seo.HOME, "a", "https://example.com", "Kulcsár Rudolf", "x" * 42):
        level, got = read_back(text)
        assert got == text
        assert level == 0b00  # error correction level M
