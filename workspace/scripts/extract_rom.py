"""City Connection (Japan).nes 원본을 PRG/CHR로 분리하고 헤더 정보를 기록한다.

사용법:
    python workspace/scripts/extract_rom.py

출력:
    extracted/header.bin, extracted/prg.bin, extracted/chr.bin,
    extracted/rom_info.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROM = ROOT / "original" / "City Connection (Japan).nes"
OUT = ROOT / "extracted"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    data = ROM.read_bytes()
    if data[:4] != b"NES\x1a":
        raise SystemExit(f"iNES 헤더가 아니다: {ROM}")

    prg_banks = data[4]
    chr_banks = data[5]
    flags6 = data[6]
    flags7 = data[7]
    mapper = (flags7 & 0xF0) | (flags6 >> 4)

    header = data[:16]
    prg_size = prg_banks * 16384
    chr_size = chr_banks * 8192
    prg = data[16 : 16 + prg_size]
    chr_ = data[16 + prg_size : 16 + prg_size + chr_size]

    if len(prg) != prg_size or len(chr_) != chr_size:
        raise SystemExit("헤더가 선언한 크기와 실제 파일 크기가 다르다")
    tail = data[16 + prg_size + chr_size :]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "header.bin").write_bytes(header)
    (OUT / "prg.bin").write_bytes(prg)
    (OUT / "chr.bin").write_bytes(chr_)

    info = {
        "rom_file": ROM.name,
        "rom_size": len(data),
        "rom_sha256": sha256(data),
        "prg_banks_16k": prg_banks,
        "chr_banks_8k": chr_banks,
        "prg_size": prg_size,
        "chr_size": chr_size,
        "flags6": f"0x{flags6:02X}",
        "flags7": f"0x{flags7:02X}",
        "mapper": mapper,
        "mirroring": "four-screen"
        if flags6 & 0x08
        else ("vertical" if flags6 & 0x01 else "horizontal"),
        "battery": bool(flags6 & 0x02),
        "trainer": bool(flags6 & 0x04),
        "prg_sha256": sha256(prg),
        "chr_sha256": sha256(chr_),
        "trailing_bytes": len(tail),
    }
    (OUT / "rom_info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
