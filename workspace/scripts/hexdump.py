"""PRG 영역을 16진수 + 폰트 타일 문자로 함께 덤프한다.

사용법:
    python workspace/scripts/hexdump.py 0xCB00 0x80
    python workspace/scripts/hexdump.py 0x0B00 0x80 --raw-offset
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRG = (ROOT / "extracted" / "prg.bin").read_bytes()

# BG 폰트(패턴 테이블 $1000) 타일 인덱스 -> 표시 문자.
# 0x30-0x39 숫자, 0x41-0x5A 영문 대문자, 0x40 공백, 그 외는 '.'로 표시한다.
def tile_char(b: int) -> str:
    if 0x30 <= b <= 0x39:
        return chr(b)
    if 0x41 <= b <= 0x5A:
        return chr(b)
    if b == 0x40:
        return "_"
    if b == 0x5B:
        return "-"
    if b == 0x5C:
        return "."
    if b == 0x5D:
        return ":"
    return "."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("addr", help="CPU 주소(0xC000~0xFFFF) 또는 --raw-offset 시 PRG 오프셋")
    ap.add_argument("length", nargs="?", default="0x40")
    ap.add_argument("--raw-offset", action="store_true")
    ap.add_argument("--width", type=int, default=16)
    args = ap.parse_args()

    addr = int(args.addr, 0)
    length = int(args.length, 0)
    off = addr if args.raw_offset else addr - 0xC000
    if not (0 <= off < len(PRG)):
        raise SystemExit(f"범위 밖: {addr:#06X}")

    for i in range(0, length, args.width):
        chunk = PRG[off + i : off + i + args.width]
        if not chunk:
            break
        hexs = " ".join(f"{b:02X}" for b in chunk)
        text = "".join(tile_char(b) for b in chunk)
        print(f"{0xC000 + off + i:04X} ({off+i:04X})  {hexs:<{args.width*3}} {text}")


if __name__ == "__main__":
    main()
