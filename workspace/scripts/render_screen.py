"""PRG의 타일 나열 블록을 실제 타일 그래픽으로 렌더해 화면 조각을 눈으로 확인한다.

포맷 가정: 0xFE = 줄바꿈, 0xFF = 종료, 그 외 = BG 타일 인덱스.
어느 패턴 테이블을 쓰는지는 화면마다 다르므로 --bank/--table로 골라 비교한다.

사용법:
    python workspace/scripts/render_screen.py 0x8D93 --bank 0 --table bg
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "work"


def load_rom(rom: str | None) -> tuple[bytes, bytes]:
    """--rom을 주면 그 .nes에서, 아니면 extracted/에서 PRG/CHR을 읽는다."""
    if not rom:
        return (ROOT / "extracted" / "prg.bin").read_bytes(), (ROOT / "extracted" / "chr.bin").read_bytes()
    data = (ROOT / rom).read_bytes()
    prg_size = data[4] * 16384
    chr_size = data[5] * 8192
    return data[16 : 16 + prg_size], data[16 + prg_size : 16 + prg_size + chr_size]

PREVIEW = [(16, 16, 24), (96, 96, 112), (176, 176, 192), (255, 255, 255)]
SCALE = 4


def decode(raw: bytes) -> list[list[int]]:
    return [
        [((raw[y] >> (7 - x)) & 1) | (((raw[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)]
        for y in range(8)
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("addr", help="CPU 주소 ($8000-$BFFF 또는 미러 $C000-$FFFF)")
    ap.add_argument("--bank", type=int, default=0)
    ap.add_argument("--table", choices=["sprite", "bg"], default="bg")
    ap.add_argument("--max-bytes", type=int, default=512)
    ap.add_argument("--rom", help="프로젝트 루트 기준 .nes 경로. 생략하면 원본 extracted/")
    ap.add_argument("--out-name", help="출력 파일명(확장자 제외)")
    args = ap.parse_args()

    PRG, CHR = load_rom(args.rom)
    addr = int(args.addr, 0)
    off = (addr - 0xC000) if addr >= 0xC000 else (addr - 0x8000)
    base = args.bank * 8192 + (0 if args.table == "sprite" else 4096)
    tiles = CHR[base : base + 4096]

    rows: list[list[int]] = [[]]
    for i in range(args.max_bytes):
        b = PRG[off + i]
        if b == 0xFF:
            break
        if b == 0xFE:
            rows.append([])
            continue
        rows[-1].append(b)
    if rows and not rows[-1]:
        rows.pop()

    w = max(len(r) for r in rows)
    img = Image.new("RGB", (w * 8, len(rows) * 8), PREVIEW[0])
    px = img.load()
    for ry, row in enumerate(rows):
        for rx, t in enumerate(row):
            tile = decode(tiles[t * 16 : t * 16 + 16])
            for y in range(8):
                for x in range(8):
                    px[rx * 8 + x, ry * 8 + y] = PREVIEW[tile[y][x]]
    img = img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)
    OUT.mkdir(parents=True, exist_ok=True)
    name = args.out_name or f"screen_{addr:04X}_b{args.bank}_{args.table}"
    out = OUT / f"{name}.png"
    img.save(out)
    print(f"{out}  rows={len(rows)} width={w}")


if __name__ == "__main__":
    main()
