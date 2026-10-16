"""PRG-ROM에서 텍스트 후보와 CHR 타일 사용 현황을 조사한다.

- CHR: 뱅크별로 빈 타일(전부 색0)과 중복 타일을 센다.
- PRG: BG 폰트가 ASCII 배치라는 가정 아래 인쇄 가능한 ASCII 문자열을 뽑는다.

사용법:
    python workspace/scripts/survey_text.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "extracted"
OUT = ROOT / "workspace" / "text" / "source"

TILE_BYTES = 16
MIN_RUN = 3


def chr_stats() -> dict:
    data = (EXTRACTED / "chr.bin").read_bytes()
    banks = []
    for b in range(len(data) // 8192):
        chunk = data[b * 8192 : (b + 1) * 8192]
        tiles = [chunk[i * TILE_BYTES : (i + 1) * TILE_BYTES] for i in range(512)]
        blank = [i for i, t in enumerate(tiles) if not any(t)]
        counts = Counter(tiles)
        dup_slots = sum(c - 1 for c in counts.values() if c > 1)
        banks.append(
            {
                "bank": b,
                "blank_tiles_total": len(blank),
                "blank_sprite_table_0x000": [i for i in blank if i < 256],
                "blank_bg_table_0x1000": [i - 256 for i in blank if i >= 256],
                "unique_tiles": len(counts),
                "duplicate_slots": dup_slots,
            }
        )
    # 두 뱅크의 동일 인덱스 타일이 같은지 비교한다.
    b0 = data[:8192]
    b1 = data[8192:16384]
    same = [i for i in range(512) if b0[i * 16 : i * 16 + 16] == b1[i * 16 : i * 16 + 16]]
    return {
        "banks": banks,
        "identical_tile_indices_count": len(same),
        "identical_bg_table_indices": [i - 256 for i in same if i >= 256],
    }


def ascii_strings(data: bytes) -> list[dict]:
    out = []
    for m in re.finditer(rb"[ -~]{%d,}" % MIN_RUN, data):
        out.append(
            {
                "prg_offset": f"0x{m.start():04X}",
                "cpu_addr_c000": f"0x{0xC000 + m.start():04X}",
                "length": len(m.group()),
                "text": m.group().decode("ascii"),
            }
        )
    return out


def main() -> None:
    prg = (EXTRACTED / "prg.bin").read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)

    report = {
        "chr": chr_stats(),
        "prg_ascii_runs": ascii_strings(prg),
    }
    (OUT / "survey_raw.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    c = report["chr"]
    for b in c["banks"]:
        print(
            f"bank{b['bank']}: blank={b['blank_tiles_total']} "
            f"(sprite {len(b['blank_sprite_table_0x000'])}, bg {len(b['blank_bg_table_0x1000'])}) "
            f"unique={b['unique_tiles']} dup_slots={b['duplicate_slots']}"
        )
    print(f"두 뱅크 동일 타일 인덱스: {c['identical_tile_indices_count']}/512")
    print(f"BG 테이블에서 두 뱅크가 동일한 인덱스 수: {len(c['identical_bg_table_indices'])}/256")
    print(f"\nASCII 후보 {len(report['prg_ascii_runs'])}건")
    for r in report["prg_ascii_runs"]:
        print(f"  {r['prg_offset']} ({r['cpu_addr_c000']}) [{r['length']:>2}] {r['text']!r}")


if __name__ == "__main__":
    main()
