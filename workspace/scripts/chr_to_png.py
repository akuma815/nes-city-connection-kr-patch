"""CHR-ROM(2bpp 8x8 타일)을 사람이 볼 수 있는 PNG 시트로 렌더한다.

사용법:
    python workspace/scripts/chr_to_png.py [--scale 3]

출력:
    work/chr_bank0.png, work/chr_bank1.png (각 8KB = 512타일, 16열 x 32행)
    타일 인덱스 눈금은 넣지 않는다. 좌표는 (행*16 + 열)로 읽는다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CHR = ROOT / "extracted" / "chr.bin"
OUT = ROOT / "work"

# NES 2bpp 색 인덱스 0~3을 회색조로 미리보기한다(실제 팔레트가 아니다).
PREVIEW = [(0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255)]

TILE_BYTES = 16
COLS = 16


def decode_tile(raw: bytes) -> list[list[int]]:
    rows = []
    for y in range(8):
        lo = raw[y]
        hi = raw[y + 8]
        rows.append([((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1) for x in range(8)])
    return rows


def render(data: bytes, scale: int) -> Image.Image:
    count = len(data) // TILE_BYTES
    rows = (count + COLS - 1) // COLS
    img = Image.new("RGB", (COLS * 8, rows * 8))
    px = img.load()
    for t in range(count):
        tile = decode_tile(data[t * TILE_BYTES : (t + 1) * TILE_BYTES])
        ox = (t % COLS) * 8
        oy = (t // COLS) * 8
        for y in range(8):
            for x in range(8):
                px[ox + x, oy + y] = PREVIEW[tile[y][x]]
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()

    data = CHR.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    for bank in range(len(data) // 8192):
        chunk = data[bank * 8192 : (bank + 1) * 8192]
        out = OUT / f"chr_bank{bank}.png"
        render(chunk, args.scale).save(out)
        print(f"{out}  ({len(chunk)//TILE_BYTES} tiles)")


if __name__ == "__main__":
    main()
