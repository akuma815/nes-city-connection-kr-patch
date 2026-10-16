"""extracted/의 header+prg+chr를 다시 접합해 ROM을 만든다.

무변경 왕복 검증(원본과 바이트 동일)도 이 스크립트로 한다.

사용법:
    python workspace/scripts/build_rom.py --verify                  # 왕복 검증만
    python workspace/scripts/build_rom.py --out build/test.nes      # 재접합 출력
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "original" / "City Connection (Japan).nes"
EXTRACTED = ROOT / "extracted"


def assemble(prg: bytes | None = None, chr_: bytes | None = None) -> bytes:
    header = (EXTRACTED / "header.bin").read_bytes()
    prg = prg if prg is not None else (EXTRACTED / "prg.bin").read_bytes()
    chr_ = chr_ if chr_ is not None else (EXTRACTED / "chr.bin").read_bytes()
    # 헤더의 뱅크 수와 실제 크기가 어긋나면 에뮬레이터가 잘못 읽는다.
    header = bytearray(header)
    header[4] = len(prg) // 16384
    header[5] = len(chr_) // 8192
    return bytes(header) + prg + chr_


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="원본과 바이트 동일한지만 확인")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rom = assemble()
    original = ORIGINAL.read_bytes()

    same = rom == original
    print(f"재접합 크기 : {len(rom)}")
    print(f"원본 크기   : {len(original)}")
    print(f"재접합 SHA  : {hashlib.sha256(rom).hexdigest()}")
    print(f"원본 SHA    : {hashlib.sha256(original).hexdigest()}")
    print(f"바이트 동일 : {'PASS' if same else 'FAIL'}")

    if not same and args.verify:
        for i, (a, b) in enumerate(zip(rom, original)):
            if a != b:
                print(f"첫 불일치 오프셋 0x{i:04X}: 재접합 0x{a:02X} vs 원본 0x{b:02X}")
                break
        raise SystemExit(1)

    if args.out:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(rom)
        print(f"출력: {out}")


if __name__ == "__main__":
    main()
