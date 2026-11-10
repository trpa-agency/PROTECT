"""Make the QR code SVGs the printable Vulnerability Assessment Guide uses.

No third-party libraries (the arcgispro-py3 env has none for QR codes). Byte mode,
error correction level M, versions 1 to 6 (up to 106 bytes), best-of-eight mask.
Follows ISO/IEC 18004 as implemented in the public-domain Nayuki QR generator.

Usage (from the repo root):
    python scripts/make_qr.py
Writes html/img/qr/<name>.svg for each entry in CODES.
"""
from __future__ import annotations

import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "html" / "img" / "qr"
SITE = "https://trpa-agency.github.io/PROTECT/html/"
FILL = "#003B71"  # TRPA Navy

CODES = {
    # Renamed Nov. 8, 2026; the old results.html and workshop-feedback.html are redirect stubs,
    # so codes already printed with the old URLs still land on these pages.
    "vulnerability-assessment": SITE + "vulnerability-assessment.html",
    "vulnerability-assessment-feedback": SITE + "vulnerability-assessment-feedback.html",
}

# Level M: version -> (total codewords, ec codewords per block, blocks). v1-6 have equal blocks.
VERSIONS_M = {1: (26, 10, 1), 2: (44, 16, 1), 3: (70, 26, 1), 4: (100, 18, 2), 5: (134, 24, 2), 6: (172, 16, 4)}
ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]}
REMAINDER_BITS = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7}
FORMAT_EC_M = 0  # L=1, M=0, Q=3, H=2

log = logging.getLogger("make_qr")

# ---- GF(256) arithmetic and Reed-Solomon ----------------------------------------------------
EXP = [0] * 512
LOG = [0] * 256
_x = 1
for _i in range(255):
    EXP[_i] = _x
    LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    EXP[_i] = EXP[_i - 255]


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return EXP[LOG[a] + LOG[b]]


def rs_generator(n: int) -> list[int]:
    g = [1]
    for i in range(n):
        ng = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            ng[j] ^= c
            ng[j + 1] ^= gf_mul(c, EXP[i])
        g = ng
    return g


def rs_ec(data: list[int], n: int) -> list[int]:
    g = rs_generator(n)
    res = list(data) + [0] * n
    for i in range(len(data)):
        c = res[i]
        if c:
            for j in range(1, len(g)):
                res[i + j] ^= gf_mul(g[j], c)
    return res[len(data):]


# ---- Encoding ------------------------------------------------------------------------------
def choose_version(nbytes: int) -> int:
    for v, (total, ec, blocks) in VERSIONS_M.items():
        data_cw = total - ec * blocks
        if data_cw * 8 - 12 >= nbytes * 8:  # 4-bit mode + 8-bit count
            return v
    raise ValueError(f"{nbytes} bytes is too long for versions 1-6 at level M (max 106)")


def codewords(data: bytes, version: int) -> list[int]:
    total, ec, blocks = VERSIONS_M[version]
    data_cw = total - ec * blocks
    bits: list[int] = []

    def put(val: int, n: int) -> None:
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)

    put(0b0100, 4)
    put(len(data), 8)
    for b in data:
        put(b, 8)
    cap = data_cw * 8
    put(0, min(4, cap - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    pad = (0xEC, 0x11)
    i = 0
    while len(bits) < cap:
        put(pad[i % 2], 8)
        i += 1
    cws = [int("".join(map(str, bits[k:k + 8])), 2) for k in range(0, cap, 8)]

    size = data_cw // blocks
    dblocks = [cws[k * size:(k + 1) * size] for k in range(blocks)]
    eblocks = [rs_ec(b, ec) for b in dblocks]
    out: list[int] = []
    for k in range(size):
        out.extend(b[k] for b in dblocks)
    for k in range(ec):
        out.extend(b[k] for b in eblocks)
    assert len(out) == total
    return out


# ---- Matrix --------------------------------------------------------------------------------
class Matrix:
    def __init__(self, version: int):
        self.v = version
        self.n = 17 + 4 * version
        self.m = [[0] * self.n for _ in range(self.n)]
        self.func = [[False] * self.n for _ in range(self.n)]

    def set_func(self, r: int, c: int, dark: bool) -> None:
        self.m[r][c] = 1 if dark else 0
        self.func[r][c] = True

    def draw_function_patterns(self) -> None:
        n = self.n
        for i in range(n):  # timing
            self.set_func(6, i, i % 2 == 0)
            self.set_func(i, 6, i % 2 == 0)
        for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):  # finders + separators
            for dr in range(-1, 8):
                for dc in range(-1, 8):
                    r, c = r0 + dr, c0 + dc
                    if 0 <= r < n and 0 <= c < n:
                        d = max(abs(dr - 3), abs(dc - 3))
                        self.set_func(r, c, d in (0, 1, 3) and -1 < dr < 7 and -1 < dc < 7)
        centers = ALIGN[self.v]
        for r0 in centers:
            for c0 in centers:
                if (r0, c0) in ((6, 6), (6, centers[-1]), (centers[-1], 6)):
                    continue
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        self.set_func(r0 + dr, c0 + dc, max(abs(dr), abs(dc)) != 1)
        self.draw_format_bits(0)  # reserve
        self.set_func(n - 8, 8, True)  # dark module

    def draw_format_bits(self, mask: int) -> None:
        data = (FORMAT_EC_M << 3) | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = ((data << 10) | rem) ^ 0x5412
        assert bits >> 15 == 0
        bit = lambda i: (bits >> i) & 1 == 1  # noqa: E731
        n = self.n
        for i in range(6):
            self.set_func(i, 8, bit(i))
        self.set_func(7, 8, bit(6))
        self.set_func(8, 8, bit(7))
        self.set_func(8, 7, bit(8))
        for i in range(9, 15):
            self.set_func(8, 14 - i, bit(i))
        for i in range(8):
            self.set_func(8, n - 1 - i, bit(i))
        for i in range(8, 15):
            self.set_func(n - 15 + i, 8, bit(i))
        self.set_func(n - 8, 8, True)

    def place_data(self, cws: list[int]) -> None:
        n = self.n
        bits = [(cw >> (7 - k)) & 1 for cw in cws for k in range(8)]
        i = 0
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            upward = ((right + 1) & 2) == 0
            for vert in range(n):
                for j in range(2):
                    c = right - j
                    r = n - 1 - vert if upward else vert
                    if not self.func[r][c] and i < len(bits):
                        self.m[r][c] = bits[i]
                        i += 1
            right -= 2

    def apply_mask(self, mask: int) -> None:
        tests = (
            lambda r, c: (r + c) % 2 == 0,
            lambda r, c: r % 2 == 0,
            lambda r, c: c % 3 == 0,
            lambda r, c: (r + c) % 3 == 0,
            lambda r, c: (r // 2 + c // 3) % 2 == 0,
            lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
            lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
            lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
        )
        t = tests[mask]
        for r in range(self.n):
            for c in range(self.n):
                if not self.func[r][c] and t(r, c):
                    self.m[r][c] ^= 1

    def penalty(self) -> int:
        n, m = self.n, self.m
        score = 0
        lines = [row[:] for row in m] + [[m[r][c] for r in range(n)] for c in range(n)]
        pat_a = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
        pat_b = pat_a[::-1]
        for line in lines:
            run, prev = 0, -1
            for x in line + [-1]:
                if x == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + run - 5
                    run, prev = 1, x
            for k in range(n - 10):
                seg = line[k:k + 11]
                if seg == pat_a or seg == pat_b:
                    score += 40
        for r in range(n - 1):
            for c in range(n - 1):
                if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                    score += 3
        dark = sum(map(sum, m))
        pct = dark * 100 // (n * n)
        score += 10 * (abs(pct - 50) // 5)
        return score


def encode(text: str) -> Matrix:
    data = text.encode("utf-8")
    version = choose_version(len(data))
    cws = codewords(data, version)
    best, best_score = None, None
    for mask in range(8):
        mx = Matrix(version)
        mx.draw_function_patterns()
        mx.place_data(cws)
        mx.apply_mask(mask)
        mx.draw_format_bits(mask)
        s = mx.penalty()
        if best_score is None or s < best_score:
            best, best_score = mx, s
    log.info("%s: version %d, %d bytes, mask penalty %d", text, version, len(data), best_score)
    return best


def to_svg(mx: Matrix, quiet: int = 4) -> str:
    n = mx.n
    d = []
    for r in range(n):
        c = 0
        while c < n:
            if mx.m[r][c]:
                start = c
                while c < n and mx.m[r][c]:
                    c += 1
                d.append(f"M{start + quiet} {r + quiet}h{c - start}v1h-{c - start}z")
            else:
                c += 1
    size = n + 2 * quiet
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges">'
        f'<rect width="{size}" height="{size}" fill="#fff"/>'
        f'<path d="{"".join(d)}" fill="{FILL}"/></svg>\n'
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in CODES.items():
        path = OUT_DIR / f"qr-{name}.svg"
        path.write_text(to_svg(encode(url)), encoding="utf-8")
        log.info("wrote %s", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
