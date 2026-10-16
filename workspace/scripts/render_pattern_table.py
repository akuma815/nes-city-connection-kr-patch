"""CHR 뱅크의 패턴 테이블 하나(256타일)를 인덱스 눈금과 함께 크게 렌더한다.

사용법:
    python workspace/scripts/render_pattern_table.py --bank 0 --table bg
    python workspace/scripts/render_pattern_table.py --bank 1 --table sprite

출력: work/pt_bank<b>_<table>.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
CHR = (ROOT / "extracted" / "chr.bin").read_bytes()
OUT = ROOT / "work"

PREVIEW = [(24, 24, 32), (96, 96, 112), (176, 176, 192), (255, 255, 255)]
SCALE = 5
PAD = 18


def decode(raw: bytes) -> list[list[int]]:
    return [
        [((raw[y] >> (7 - x)) & 1) | (((raw[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)]
        for y in range(8)
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", type=int, required=True)
    ap.add_argument("--table", choices=["sprite", "bg"], required=True)
    args = ap.parse_args()

    base = args.bank * 8192 + (0 if args.table == "sprite" else 4096)
    data = CHR[base : base + 4096]

    cell = 8 * SCALE + 1
    img = Image.new("RGB", (PAD + 16 * cell, PAD + 16 * cell), (40, 40, 48))
    d = ImageDraw.Draw(img)
    for t in range(256):
        tile = decode(data[t * 16 : t * 16 + 16])
        ox = PAD + (t % 16) * cell
        oy = PAD + (t // 16) * cell
        for y in range(8):
            for x in range(8):
                c = PREVIEW[tile[y][x]]
                d.rectangle(
                    [ox + x * SCALE, oy + y * SCALE, ox + x * SCALE + SCALE - 1, oy + y * SCALE + SCALE - 1],
                    fill=c,
                )
    for i in range(16):
        d.text((PAD + i * cell + cell // 2 - 4, 4), f"{i:X}", fill=(255, 220, 120))
        d.text((4, PAD + i * cell + cell // 2 - 4), f"{i:X}", fill=(255, 220, 120))

    out = OUT / f"pt_bank{args.bank}_{args.table}.png"
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
