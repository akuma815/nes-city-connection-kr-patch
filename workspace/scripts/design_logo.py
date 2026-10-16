"""타이틀 로고를 한글로 다시 그린다.

제약(모두 docs/survey.md와 실측에서 나온 값이다):
  - 타일 데이터는 `$8D94`부터 **118바이트** 안에 끝나야 한다. 그 뒤는 엔딩 문구다.
  - 화면 시작 위치는 PPUADDR `$2105` = 8행 5열. `0xFE`마다 다음 행의 **같은 열 5**로 간다.
  - 한 행은 5열부터라 최대 27칸이다.
  - 쓸 수 있는 서로 다른 타일은 `analyze_logo.py`가 계산한 안전 목록뿐이다(현재 32개).
    빈 칸은 PT0의 빈 타일 `0x40`을 그대로 쓰므로 예산에 들어가지 않는다.

사용법:
    # 여러 폰트·크기를 훑어 유니크 타일 수만 비교
    python workspace/scripts/design_logo.py --probe
    # 하나 골라 미리보기와 패치 설정 생성
    python workspace/scripts/design_logo.py --font Galmuri11-Condensed.ttf --size 22 --emit
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT.parents[1] / "Font"
OUT = ROOT / "work"
CONFIG = ROOT / "workspace" / "config"

LOGO_ADDR = 0x8D94
LOGO_MAX_BYTES = 118
START_COL = 5
MAX_ROW_CELLS = 32 - START_COL
BLANK_TILE = 0x40

# analyze_logo.py의 [A] + [B1]. 0x50은 게임 스프라이트가 써서 뺐다.
SAFE_TILES = [
    0x3E, 0x3F, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x4B, 0x4C,
    0x4D, 0x4E, 0x4F, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x5B,
    0x5C, 0x5D, 0x5E, 0x5F,
]

CANVAS_COLS = 21
CANVAS_ROWS = 6


def load(font_file: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / font_file), size)


def _ink_box(font_file: str, size: int, text: str, spacing: int) -> tuple[int, int, int, int]:
    """넉넉한 캔버스에 한 번 그려 실제 잉크 경계를 잰다. 폰트마다 여백이 달라 계산에 기댈 수 없다."""
    pad = size * 3
    tmp = Image.new("L", (size * len(text) * 2 + pad * 2, size * 3 + pad * 2), 0)
    d = ImageDraw.Draw(tmp)
    f = load(font_file, size)
    cx = pad
    for ch in text:
        d.text((cx, pad), ch, font=f, fill=255)
        cx += int(d.textlength(ch, font=f)) + spacing
    bb = tmp.point(lambda v: 255 if v >= 128 else 0).getbbox()
    return bb if bb else (pad, pad, pad, pad)


def render(font_file: str, size: int, lines: list[tuple[str, int, int, int]], threshold: int) -> Image.Image:
    """lines: (텍스트, x, y, 자간). x가 None이면 가로 중앙 정렬한다. 캔버스는 21x6 타일 = 168x48."""
    img = Image.new("L", (CANVAS_COLS * 8, CANVAS_ROWS * 8), 0)
    d = ImageDraw.Draw(img)
    f = load(font_file, size)
    for text, x, y, spacing in lines:
        if x is None:
            bb = _ink_box(font_file, size, text, spacing)
            pad = size * 3
            width = bb[2] - bb[0]
            x = (img.width - width) // 2 - (bb[0] - pad)
        cx = x
        for ch in text:
            d.text((cx, y), ch, font=f, fill=255)
            cx += int(d.textlength(ch, font=f)) + spacing
    return img.point(lambda v: 255 if v >= threshold else 0)


BLANK = bytes(64)


def _shift(mask: Image.Image, dx: int, dy: int) -> Image.Image:
    out = Image.new("L", mask.size, 0)
    out.paste(mask, (dx, dy))
    return out


def _dilate1(mask: Image.Image) -> Image.Image:
    """상하좌우 1픽셀 팽창. 대각선은 빼서 테두리가 뭉치지 않게 한다."""
    out = mask.copy()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out = ImageChops.lighter(out, _shift(mask, dx, dy))
    return out


def compose_layers(
    body: Image.Image,
    body_color: int,
    outline_color: int,
    shadow_px: int,
) -> Image.Image:
    """본체·테두리·그림자를 겹쳐 색 인덱스(0~3) 이미지를 만든다.

    원본 로고와 같은 구성이다. 본체 값 2(분홍), 테두리 값 1(흰) 또는 3(살구), 그림자 값 3.
    테두리는 붙어 있는 음절끼리 서로 먹히지 않게 갈라 주는 역할을 한다.
    """
    val = Image.new("L", body.size, 0)
    if shadow_px:
        sh = _shift(body, shadow_px, shadow_px)
        if outline_color:
            sh = ImageChops.lighter(sh, _shift(_dilate1(body), shadow_px, shadow_px))
        val.paste(3, (0, 0), sh)
    if outline_color:
        ring = ImageChops.subtract(_dilate1(body), body)
        val.paste(outline_color, (0, 0), ring)
    val.paste(body_color, (0, 0), body)
    return val


def value_image_to_grid(val: Image.Image) -> list[list[bytes]]:
    px = val.load()
    grid: list[list[bytes]] = []
    for r in range(CANVAS_ROWS):
        row = []
        for c in range(CANVAS_COLS):
            cell = bytearray(64)
            for y in range(8):
                for x in range(8):
                    cell[y * 8 + x] = px[c * 8 + x, r * 8 + y]
            row.append(bytes(cell))
        grid.append(row)
    return grid


def to_value_grid(body: Image.Image, shadow: Image.Image | None, body_color: int) -> list[list[bytes]]:
    """캔버스를 8x8 타일로 자르고 각 픽셀을 NES 색 인덱스(0~3)로 담는다.

    원본 로고는 본체 값 2, 그림자 값 3을 쓴다. 같은 규칙을 따르면 팔레트를 안 건드린다.
    """
    bp = body.load()
    sp = shadow.load() if shadow is not None else None
    grid: list[list[bytes]] = []
    for r in range(CANVAS_ROWS):
        row = []
        for c in range(CANVAS_COLS):
            cell = bytearray(64)
            for y in range(8):
                for x in range(8):
                    px, py = c * 8 + x, r * 8 + y
                    if bp[px, py]:
                        cell[y * 8 + x] = body_color
                    elif sp is not None and sp[px, py]:
                        cell[y * 8 + x] = 3
            row.append(bytes(cell))
        grid.append(row)
    return grid


def value_tile_to_2bpp(cell: bytes) -> bytes:
    """64개 색 인덱스를 NES 2bpp 플레이너 16바이트로."""
    plane0 = bytearray(8)
    plane1 = bytearray(8)
    for y in range(8):
        b0 = b1 = 0
        for x in range(8):
            v = cell[y * 8 + x]
            if v & 1:
                b0 |= 1 << (7 - x)
            if v & 2:
                b1 |= 1 << (7 - x)
        plane0[y] = b0
        plane1[y] = b1
    return bytes(plane0) + bytes(plane1)


def _dist(a: bytes, b: bytes) -> int:
    """다른 픽셀 개수. 값이 다르면 1로 센다."""
    return sum(1 for x, y in zip(a, b) if x != y)


def reduce_tiles(grid: list[list[bytes]], limit: int) -> tuple[list[list[bytes]], int]:
    """유니크 타일이 예산을 넘으면 가장 비슷한 타일끼리 합친다.

    글자 모양을 다시 디자인하는 대신 픽셀 몇 개를 양보한다. 드물게 쓰이는 타일을
    가장 가까운 이웃으로 흡수시키므로 화면상 차이가 가장 작은 쪽부터 사라진다.
    """
    blank = BLANK
    counts: dict[bytes, int] = {}
    for row in grid:
        for t in row:
            if t != blank:
                counts[t] = counts.get(t, 0) + 1

    remap: dict[bytes, bytes] = {}
    merges = 0
    while len(counts) > limit:
        keys = list(counts)
        best = None
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                d = _dist(keys[i], keys[j])
                # 덜 쓰이는 쪽을 흡수시킨다.
                a, b = (keys[i], keys[j]) if counts[keys[i]] >= counts[keys[j]] else (keys[j], keys[i])
                score = (d, counts[b])
                if best is None or score < best[0]:
                    best = (score, a, b)
        if best is None:
            break
        _, keep, drop = best
        for k, v in list(remap.items()):
            if v == drop:
                remap[k] = keep
        remap[drop] = keep
        counts[keep] += counts.pop(drop)
        merges += 1

    if not remap:
        return grid, 0
    out = [[remap.get(t, t) for t in row] for row in grid]
    return out, merges


# 미리보기용 색. 실제 화면 색은 게임 팔레트가 정한다.
PREVIEW_RGB = {0: (0, 0, 0), 1: (255, 255, 255), 2: (240, 140, 200), 3: (230, 120, 90)}


def from_tiles(grid: list[list[bytes]]) -> Image.Image:
    """타일 격자를 다시 이미지로. 병합 결과를 눈으로 확인할 때 쓴다."""
    img = Image.new("RGB", (CANVAS_COLS * 8, CANVAS_ROWS * 8), (0, 0, 0))
    px = img.load()
    for r, row in enumerate(grid):
        for c, t in enumerate(row):
            for y in range(8):
                for x in range(8):
                    px[c * 8 + x, r * 8 + y] = PREVIEW_RGB[t[y * 8 + x]]
    return img


def measure(grid: list[list[bytes]]) -> tuple[int, int]:
    """(빈 타일 제외 유니크 수, 데이터 바이트 수)"""
    blank = BLANK
    uniq = {t for row in grid for t in row if t != blank}
    # 각 행의 오른쪽 빈 칸은 잘라내도 화면이 같다. 줄바꿈 1바이트 + 마지막 종료 1바이트.
    total = 0
    for row in grid:
        last = -1
        for i, t in enumerate(row):
            if t != blank:
                last = i
        total += (last + 1) + 1  # 잘라낸 행 + 0xFE
    return len(uniq), total  # 마지막 0xFE를 0xFF로 바꾸므로 추가 바이트 없음


CANVAS_H = CANVAS_ROWS * 8


def render_grid(
    font_file: str,
    size: int,
    lines: list[tuple[str, int, int]],
    cell_w: int,
    cell_h: int,
    threshold: int,
) -> Image.Image:
    """음절을 타일 격자 칸에 하나씩 맞춰 그린다.

    글자를 8px 격자에 정렬하면 서로 다른 음절이라도 같은 8x8 조각을 공유할 확률이 올라간다.
    유니크 타일 예산이 빡빡할 때 자유 배치보다 유리하다.

    lines: (텍스트, 시작 열, 시작 행) — 단위는 타일.
    """
    img = Image.new("L", (CANVAS_COLS * 8, CANVAS_H), 0)
    f = load(font_file, size)
    for text, col0, row0 in lines:
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            # 각 음절을 넉넉히 그린 뒤 잉크만 잘라 칸 중앙에 붙인다.
            pad = size * 2
            tmp = Image.new("L", (size * 2 + pad * 2, size * 2 + pad * 2), 0)
            ImageDraw.Draw(tmp).text((pad, pad), ch, font=f, fill=255)
            tmp = tmp.point(lambda v: 255 if v >= threshold else 0)
            bb = tmp.getbbox()
            if not bb:
                continue
            glyph = tmp.crop(bb)
            cw, chh = cell_w * 8, cell_h * 8
            if glyph.width > cw or glyph.height > chh:
                glyph = glyph.crop((0, 0, min(glyph.width, cw), min(glyph.height, chh)))
            ox = (col0 + i * cell_w) * 8 + (cw - glyph.width) // 2
            oy = row0 * 8 + (chh - glyph.height) // 2
            img.paste(glyph, (ox, oy), glyph)
    return img.point(lambda v: 255 if v >= threshold else 0)

LAYOUTS = {
    # 한 줄: "시티 커넥션". 세로 중앙.
    "1line": lambda size: [("시티 커넥션", None, (CANVAS_H - size) // 2, 0)],
    # 두 줄: 위 "시티", 아래 "커넥션". 두 줄이 48px 안에 들어가야 한다.
    "2line": lambda size: [("시티", None, 0, 0), ("커넥션", None, CANVAS_H - size, 0)],
    # 원본 구성 흉내: 작은 "시티" 위, 큰 "커넥션" 아래
    "small_big": lambda size: [("시티", None, 0, 0), ("커넥션", None, CANVAS_H - size, 0)],
}


def probe() -> None:
    fonts = [
        "Galmuri11-Condensed.ttf",
        "Galmuri9.ttf",
        "Galmuri7.ttf",
        "neodgm.ttf",
        "HancomMalangMalang-Bold.ttf",
        "Hangeuljaemin4-Regular.ttf",
        "SinchonRhapsodyTTF-ExtraBold_(2).ttf",
        "RiaSans-ExtraBold.ttf",
        "dalmoori.ttf",
    ]
    print(f"{'폰트':<40} {'배치':<6} {'크기':>4} {'유니크':>6} {'바이트':>6}  판정")
    print("-" * 84)
    best = []
    for fn in fonts:
        for layout in ("1line", "2line"):
            for size in range(12, 33, 2):
                try:
                    lines = LAYOUTS[layout](size)
                    img = render(fn, size, lines, 128)
                except OSError:
                    continue
                grid = to_value_grid(img, None, 2)
                uniq, nbytes = measure(grid)
                ok = uniq <= len(SAFE_TILES) and nbytes <= LOGO_MAX_BYTES
                if ok:
                    best.append((uniq, nbytes, fn, layout, size))
                mark = "OK" if ok else ("타일초과" if uniq > len(SAFE_TILES) else "길이초과")
                if ok or uniq <= len(SAFE_TILES) + 12:
                    print(f"{fn:<40} {layout:<6} {size:>4} {uniq:>6} {nbytes:>6}  {mark}")
    print(f"\n통과 조합 {len(best)}개. 유니크 타일이 적은 순:")
    for u, n, fn, layout, size in sorted(best)[:15]:
        print(f"  유니크 {u:>3}  바이트 {n:>3}  {fn} {layout} {size}px")


SHEET = [
    ("Galmuri11-Condensed.ttf", "1line", 24),
    ("Galmuri7.ttf", "1line", 24),
    ("neodgm.ttf", "1line", 24),
    ("HancomMalangMalang-Bold.ttf", "1line", 24),
    ("Hangeuljaemin4-Regular.ttf", "1line", 24),
    ("dalmoori.ttf", "1line", 24),
    ("SinchonRhapsodyTTF-ExtraBold_(2).ttf", "1line", 24),
    ("RiaSans-ExtraBold.ttf", "1line", 24),
    ("Galmuri11-Condensed.ttf", "2line", 24),
    ("neodgm.ttf", "2line", 24),
    ("HancomMalangMalang-Bold.ttf", "2line", 24),
    ("Hangeuljaemin4-Regular.ttf", "2line", 24),
    ("SinchonRhapsodyTTF-ExtraBold_(2).ttf", "2line", 24),
    ("RiaSans-ExtraBold.ttf", "2line", 24),
    ("dalmoori.ttf", "2line", 24),
    ("Galmuri7.ttf", "2line", 24),
]


# 격자 배치 후보. (폰트, 글자크기, 줄들, 칸 너비, 칸 높이)
# 줄은 (텍스트, 시작 열, 시작 행) — 21열 6행 안에 들어가야 한다.
GRID_SHEET = [
    # 한 줄, 음절당 3x3 타일(24px). 6음절 = 18열.
    ("Galmuri11-Condensed.ttf", 24, [("시티커넥션", 3, 1)], 3, 3),
    ("neodgm.ttf", 24, [("시티커넥션", 3, 1)], 3, 3),
    ("HancomMalangMalang-Bold.ttf", 24, [("시티커넥션", 3, 1)], 3, 3),
    ("RiaSans-ExtraBold.ttf", 24, [("시티커넥션", 3, 1)], 3, 3),
    ("SinchonRhapsodyTTF-ExtraBold_(2).ttf", 24, [("시티커넥션", 3, 1)], 3, 3),
    ("dalmoori.ttf", 24, [("시티커넥션", 3, 1)], 3, 3),
    # 두 줄, 음절당 3x3. 위 "시티"(6열) 아래 "커넥션"(9열), 합 6행.
    ("Galmuri11-Condensed.ttf", 24, [("시티", 7, 0), ("커넥션", 6, 3)], 3, 3),
    ("neodgm.ttf", 24, [("시티", 7, 0), ("커넥션", 6, 3)], 3, 3),
    ("HancomMalangMalang-Bold.ttf", 24, [("시티", 7, 0), ("커넥션", 6, 3)], 3, 3),
    ("RiaSans-ExtraBold.ttf", 24, [("시티", 7, 0), ("커넥션", 6, 3)], 3, 3),
    ("SinchonRhapsodyTTF-ExtraBold_(2).ttf", 24, [("시티", 7, 0), ("커넥션", 6, 3)], 3, 3),
    ("dalmoori.ttf", 24, [("시티", 7, 0), ("커넥션", 6, 3)], 3, 3),
    # 두 줄, 음절당 2x3(16x24) — 가로로 좁혀 유니크를 줄인다.
    ("Galmuri11-Condensed.ttf", 24, [("시티", 8, 0), ("커넥션", 7, 3)], 2, 3),
    ("neodgm.ttf", 24, [("시티", 8, 0), ("커넥션", 7, 3)], 2, 3),
    ("RiaSans-ExtraBold.ttf", 24, [("시티", 8, 0), ("커넥션", 7, 3)], 2, 3),
    ("SinchonRhapsodyTTF-ExtraBold_(2).ttf", 24, [("시티", 8, 0), ("커넥션", 7, 3)], 2, 3),
]


def grid_sheet(threshold: int) -> None:
    scale = 3
    w, h = CANVAS_COLS * 8 * scale, CANVAS_ROWS * 8 * scale
    label = 15
    cols = 2
    rows = (len(GRID_SHEET) + cols - 1) // cols
    img = Image.new("RGB", (cols * (w + 6), rows * (h + label + 6)), (20, 20, 28))
    d = ImageDraw.Draw(img)
    for i, (fn, size, lines, cw, ch) in enumerate(GRID_SHEET):
        try:
            g = render_grid(fn, size, lines, cw, ch, threshold)
        except OSError:
            continue
        grid = to_value_grid(g, None, 2)
        raw_uniq, _ = measure(grid)
        grid, merges = reduce_tiles(grid, len(SAFE_TILES))
        uniq, nbytes = measure(grid)
        ok = uniq <= len(SAFE_TILES) and nbytes <= LOGO_MAX_BYTES
        x = (i % cols) * (w + 6) + 3
        y = (i // cols) * (h + label + 6) + 3
        img.paste(from_tiles(grid).convert("RGB").resize((w, h), Image.NEAREST), (x, y))
        color = (140, 255, 140) if ok else (255, 130, 130)
        d.text(
            (x + 2, y + h + 1),
            f"{i}: {fn} {size}px cell{cw}x{ch}  원래{raw_uniq}->{uniq} 병합{merges} {nbytes}B {'OK' if ok else 'X'}",
            fill=color,
        )
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "logo_grid_candidates.png"
    img.save(out)
    print(out)


def sheet(threshold: int) -> None:
    scale = 3
    w, h = CANVAS_COLS * 8 * scale, CANVAS_ROWS * 8 * scale
    label = 15
    cols = 2
    rows = (len(SHEET) + cols - 1) // cols
    img = Image.new("RGB", (cols * (w + 6), rows * (h + label + 6)), (20, 20, 28))
    d = ImageDraw.Draw(img)
    for i, (fn, layout, size) in enumerate(SHEET):
        try:
            g = render(fn, size, LAYOUTS[layout](size), threshold)
        except OSError:
            continue
        grid = to_value_grid(g, None, 2)
        uniq, nbytes = measure(grid)
        ok = uniq <= len(SAFE_TILES) and nbytes <= LOGO_MAX_BYTES
        x = (i % cols) * (w + 6) + 3
        y = (i // cols) * (h + label + 6) + 3
        img.paste(g.convert("RGB").resize((w, h), Image.NEAREST), (x, y))
        color = (140, 255, 140) if ok else (255, 130, 130)
        d.text((x + 2, y + h + 1), f"{i}: {fn} {layout} {size}px  유니크{uniq} {nbytes}B {'OK' if ok else 'X'}", fill=color)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "logo_candidates.png"
    img.save(out)
    print(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--grid-sheet", action="store_true")
    ap.add_argument("--font", default="Galmuri11-Condensed.ttf")
    ap.add_argument("--size", type=int, default=16)
    ap.add_argument("--layout", default="1line", choices=list(LAYOUTS))
    ap.add_argument(
        "--grid",
        help="격자 배치. '텍스트:시작열:시작행' 을 쉼표로 나열한다. 예: 시티:7:0,커넥션:6:3",
    )
    ap.add_argument("--cell-w", type=int, default=3, help="격자 칸 너비(타일)")
    ap.add_argument("--cell-h", type=int, default=3, help="격자 칸 높이(타일)")
    ap.add_argument(
        "--color",
        type=int,
        default=2,
        choices=[1, 2, 3],
        help="글리프 픽셀 값. 원본 로고 본체가 2(분홍)다",
    )
    ap.add_argument(
        "--shadow",
        type=int,
        default=0,
        metavar="PX",
        help="본체 아래·오른쪽에 값 3 그림자를 몇 픽셀 깔지. 0이면 없음",
    )
    ap.add_argument(
        "--outline",
        type=int,
        default=0,
        choices=[0, 1, 2, 3],
        help="본체 둘레 1px 테두리 색. 1이면 흰색이라 붙은 음절이 갈라진다. 0이면 없음",
    )
    ap.add_argument("--threshold", type=int, default=128)
    ap.add_argument("--emit", action="store_true", help="미리보기와 패치 설정을 만든다")
    args = ap.parse_args()

    if args.probe:
        probe()
        return
    if args.sheet:
        sheet(args.threshold)
        return
    if args.grid_sheet:
        grid_sheet(args.threshold)
        return

    if args.grid:
        lines = [(t, int(c), int(r)) for t, c, r in (s.split(":") for s in args.grid.split(","))]
        img = render_grid(args.font, args.size, lines, args.cell_w, args.cell_h, args.threshold)
        desc = f"{args.font} {args.size}px grid{args.cell_w}x{args.cell_h} {args.grid}"
    else:
        img = render(args.font, args.size, LAYOUTS[args.layout](args.size), args.threshold)
        desc = f"{args.font} {args.size}px {args.layout}"

    if args.shadow:
        desc += f" +그림자{args.shadow}px"
    if args.outline:
        desc += f" +테두리(값{args.outline})"
    grid = value_image_to_grid(compose_layers(img, args.color, args.outline, args.shadow))
    raw_uniq, _ = measure(grid)
    grid, merges = reduce_tiles(grid, len(SAFE_TILES))
    uniq, nbytes = measure(grid)
    print(f"{desc}\n  유니크 {raw_uniq} -> {uniq} (병합 {merges}) / 한도 {len(SAFE_TILES)}")
    print(f"  데이터 {nbytes}바이트 / 한도 {LOGO_MAX_BYTES}")

    OUT.mkdir(parents=True, exist_ok=True)
    preview = from_tiles(grid).convert("RGB").resize((img.width * 4, img.height * 4), Image.NEAREST)
    preview.save(OUT / "logo_preview.png")
    print(f"  미리보기: {OUT / 'logo_preview.png'}")

    if not args.emit:
        return
    if uniq > len(SAFE_TILES) or nbytes > LOGO_MAX_BYTES:
        raise SystemExit("한도를 넘어 설정을 만들지 않는다")

    blank = BLANK
    assign: dict[bytes, int] = {blank: BLANK_TILE}
    pool = list(SAFE_TILES)
    glyphs = []
    for row in grid:
        for t in row:
            if t not in assign:
                idx = pool.pop(0)
                assign[t] = idx
                # 이미 색 인덱스가 들어 있는 타일이라 2bpp 16바이트를 그대로 넘긴다.
                glyphs.append(
                    {
                        "tile": f"0x{idx:02X}",
                        "table": "sprite",
                        "banks": [0],
                        "bytes": value_tile_to_2bpp(t).hex(),
                    }
                )

    data = bytearray()
    for row in grid:
        last = -1
        for i, t in enumerate(row):
            if t != blank:
                last = i
        data.extend(assign[t] for t in row[: last + 1])
        data.append(0xFE)
    data[-1] = 0xFF

    # 원본 블록과 길이를 맞춘다. 0xFF 뒤는 그리기 루틴이 읽지 않으므로 0xFF로 채운다.
    prg = (ROOT / "extracted" / "prg.bin").read_bytes()
    off = LOGO_ADDR - 0x8000
    original = prg[off : off + LOGO_MAX_BYTES]
    if len(data) > LOGO_MAX_BYTES:
        raise SystemExit(f"데이터 {len(data)}바이트 > 한도 {LOGO_MAX_BYTES}")
    data += bytes([0xFF] * (LOGO_MAX_BYTES - len(data)))

    cfg = {
        "name": "logo_kr",
        "description": f"타이틀 로고를 '시티 커넥션'으로 교체 ({desc})",
        "_constraints": (
            f"$8D94부터 {LOGO_MAX_BYTES}바이트 고정, 유니크 타일 {len(SAFE_TILES)}개 이내, "
            "화면 8행 5열 시작, 0xFE=줄바꿈 0xFF=끝"
        ),
        "_tiles_are_pt0_bank0": "로고는 PT0을 쓰고 타이틀 화면은 CHR 뱅크 0이다. 뱅크 1은 건드리지 않는다.",
        "glyphs": glyphs,
        "strings": [
            {
                "id": "title_logo_tilemap",
                "addr": f"0x{LOGO_ADDR:04X}",
                "original": " ".join(f"{b:02X}" for b in original),
                "tiles": " ".join(f"{b:02X}" for b in data),
            }
        ],
    }
    out = CONFIG / "patch_logo.json"
    out.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  설정: {out}  (타일 {len(glyphs)}종, 데이터 {nbytes}바이트 + 패딩)")


if __name__ == "__main__":
    main()
