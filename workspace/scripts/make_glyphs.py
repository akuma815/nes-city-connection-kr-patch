"""Galmuri8x8에서 8x8 한글 글리프를 굽고 NES 2bpp 타일로 만든다.

NES BG 팔레트를 원본 그대로 두려고 픽셀은 색 0(배경)과 색 3(가장 밝은 색)만 쓴다.
원본 영문 폰트도 색 3 한 가지로만 그려져 있어 같은 팔레트로 그대로 표시된다.

글자별로 잉크를 중앙 정렬하면 기준선이 흔들린다. 여기서는 표본 음절 전체의 잉크
경계를 한 번 재서 **전 글자 공통 원점**을 잡고 그 원점으로만 그린다.

사용법:
    python workspace/scripts/make_glyphs.py --check            # 공통 원점·8x8 수용 여부 검사
    python workspace/scripts/make_glyphs.py --preview "준비게임오버"
    python workspace/scripts/make_glyphs.py --tiles "준비"      # 16바이트 타일 덤프
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = ROOT.parents[1] / "Font"
OUT = ROOT / "work"

FONT_FILE = "Galmuri8x8.ttf"
FONT_SIZE = 16  # 이 폰트는 16ppem 스트라이크에서만 열리며 그 크기에서 잉크가 8x8이다.
CANVAS = 24
DRAW_AT = (4, 4)
THRESHOLD = 128

# 공통 원점 측정용 표본. 받침 유무·모음 방향이 다른 글자를 섞는다.
# Galmuri8x8은 완성형 부분집합이라 '힣' 같은 일부 음절이 없다. 표본에는 실제로 쓸 글자만 넣고,
# 번역문에 쓸 글자는 --coverage로 따로 검사한다.
SAMPLE = "가준비게임오버워프보너스기름점높이최고모든속도로를달렸다인용을계속끝일시정지"

_font: ImageFont.FreeTypeFont | None = None
_origin: tuple[int, int] | None = None


def font() -> ImageFont.FreeTypeFont:
    global _font
    if _font is None:
        _font = ImageFont.truetype(str(FONT_DIR / FONT_FILE), FONT_SIZE)
    return _font


def _raw_mask(ch: str) -> Image.Image:
    img = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(img).text(DRAW_AT, ch, font=font(), fill=255)
    return img.point(lambda v: 255 if v >= THRESHOLD else 0)


def origin() -> tuple[int, int]:
    """표본 전체 잉크를 감싸는 좌상단. 모든 글자가 이 원점을 공유한다."""
    global _origin
    if _origin is None:
        x0 = y0 = 10**9
        for ch in SAMPLE:
            bb = _raw_mask(ch).getbbox()
            if bb:
                x0, y0 = min(x0, bb[0]), min(y0, bb[1])
        _origin = (x0, y0)
    return _origin


def glyph_mask(ch: str) -> list[list[int]]:
    """공통 원점 기준 8x8 0/1 마스크."""
    ox, oy = origin()
    px = _raw_mask(ch).load()
    return [[1 if px[ox + x, oy + y] else 0 for x in range(8)] for y in range(8)]


def glyph_tile(ch: str) -> bytes:
    """NES 2bpp 타일 16바이트. 값 0과 값 3만 쓴다."""
    rows = bytearray(8)
    for y, line in enumerate(glyph_mask(ch)):
        b = 0
        for x, v in enumerate(line):
            if v:
                b |= 1 << (7 - x)
        rows[y] = b
    return bytes(rows) * 2  # plane0 == plane1 -> 픽셀 값 3


def check() -> int:
    ox, oy = origin()
    print(f"공통 원점: ({ox}, {oy})  (캔버스 {CANVAS}, draw at {DRAW_AT})")
    bad = []
    for ch in SAMPLE:
        bb = _raw_mask(ch).getbbox()
        if bb is None:
            bad.append((ch, "글리프 없음"))
            continue
        w, h = bb[2] - ox, bb[3] - oy
        if w > 8 or h > 8:
            bad.append((ch, f"8x8 초과 {w}x{h}"))
    if bad:
        for ch, why in bad:
            print(f"  FAIL {ch}: {why}")
        return 1
    print(f"표본 {len(SAMPLE)}자 전부 공통 원점 기준 8x8 안에 들어간다. PASS")
    return 0


def coverage(chars: str) -> int:
    """번역문에 쓸 글자가 폰트에 있고 8x8에 들어가는지 검사한다."""
    ox, oy = origin()
    bad = []
    for ch in dict.fromkeys(chars):
        if ch in " \n":
            continue
        bb = _raw_mask(ch).getbbox()
        if bb is None:
            bad.append((ch, "폰트에 글리프 없음"))
        elif bb[2] - ox > 8 or bb[3] - oy > 8:
            bad.append((ch, f"8x8 초과 {bb[2]-ox}x{bb[3]-oy}"))
    uniq = len({c for c in chars if c not in " \n"})
    for ch, why in bad:
        print(f"  FAIL {ch}: {why}")
    print(f"고유 {uniq}자 중 {uniq - len(bad)}자 사용 가능")
    return 1 if bad else 0


def preview(chars: str) -> None:
    scale = 12
    cell = 8 * scale + 3
    per_row = 8
    rows = (len(chars) + per_row - 1) // per_row
    img = Image.new("RGB", (per_row * cell, rows * cell), (30, 30, 36))
    d = ImageDraw.Draw(img)
    for i, ch in enumerate(chars):
        mask = glyph_mask(ch)
        ox, oy = (i % per_row) * cell, (i // per_row) * cell
        for y in range(8):
            for x in range(8):
                c = (255, 255, 255) if mask[y][x] else (18, 18, 24)
                d.rectangle(
                    [ox + x * scale, oy + y * scale, ox + x * scale + scale - 1, oy + y * scale + scale - 1],
                    fill=c,
                )
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "glyph_preview.png"
    img.save(out)
    print(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--coverage", metavar="CHARS")
    ap.add_argument("--preview", metavar="CHARS")
    ap.add_argument("--tiles", metavar="CHARS")
    args = ap.parse_args()

    rc = 0
    if args.check:
        rc = check()
    if args.coverage:
        rc |= coverage(args.coverage)
    if args.preview:
        preview(args.preview)
    if args.tiles:
        for ch in args.tiles:
            print(f"{ch}: " + " ".join(f"{b:02X}" for b in glyph_tile(ch)))
    if not (args.check or args.coverage or args.preview or args.tiles):
        ap.print_help()
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
