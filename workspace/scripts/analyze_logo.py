"""타이틀 로고(PT0)를 다시 그릴 때 쓸 수 있는 타일 예산을 계산한다.

로고는 `$8D93`의 21×6 타일맵이고 PT0(패턴 테이블 0)을 쓴다.
PT0는 게임 플레이 중 **스프라이트**도 쓰므로, 스프라이트가 쓰는 인덱스는 건드리면 안 된다.

사용법:
    python workspace/scripts/analyze_logo.py work/qa/spr_stage0 work/qa/spr_stage1 ...
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRG = (ROOT / "extracted" / "prg.bin").read_bytes()

LOGO_ADDR = 0x8D93
LOGO_WIDTH = 21


def logo_tilemap() -> list[list[int]]:
    off = LOGO_ADDR - 0x8000
    rows: list[list[int]] = [[]]
    i = 0
    while True:
        b = PRG[off + i]
        i += 1
        if b == 0xFF:
            break
        if b == 0xFE:
            rows.append([])
            continue
        rows[-1].append(b)
    if rows and not rows[-1]:
        rows.pop()
    return rows


def usage(runs: list[str], filename: str, header: str) -> dict[int, Counter]:
    """{패턴테이블주소: Counter{tile: 횟수}}"""
    merged: dict[int, Counter] = defaultdict(Counter)
    for r in runs:
        p = ROOT / r / filename
        if not p.exists():
            print(f"건너뜀(없음): {p}")
            continue
        pt = None
        for line in p.read_text(encoding="utf-8").splitlines():
            m = re.match(rf"#\s*{header}=\$([0-9A-Fa-f]+)", line)
            if m:
                pt = int(m.group(1), 16)
                continue
            m = re.match(r"([0-9A-Fa-f]{2})\s+(\d+)", line)
            if m and pt is not None:
                merged[pt][int(m.group(1), 16)] += int(m.group(2))
    return merged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="sprite_tile_usage.txt가 있는 QA 폴더들")
    args = ap.parse_args()

    rows = logo_tilemap()
    used = Counter(t for row in rows for t in row)
    print(f"로고 타일맵: {len(rows)}행 × 최대 {max(len(r) for r in rows)}열, 셀 {sum(len(r) for r in rows)}개")
    print(f"쓰이는 서로 다른 타일: {len(used)}종\n")
    for row in rows:
        print("   " + " ".join(f"{t:02X}" for t in row))
    print()

    spr_pt0 = usage(args.runs, "sprite_tile_usage.txt", "spritePatternAddr").get(0x0000, Counter())
    # 타이틀 화면은 BG도 PT0을 쓴다. 점수 숫자·저작권 기호가 여기 들어간다.
    bg_pt0 = usage(args.runs, "bg_tile_usage.txt", "backgroundPatternAddr").get(0x0000, Counter())
    print(f"게임 플레이 중 PT0 스프라이트가 쓰는 타일: {len(spr_pt0)}종")
    print(f"타이틀 화면 BG가 PT0에서 쓰는 타일: {len(bg_pt0)}종")

    logo_set = set(used)
    # 타이틀 BG 사용분 중 로고가 아닌 것 = 점수 숫자 등. 이건 로고와 무관하게 보존해야 한다.
    bg_non_logo = set(bg_pt0) - logo_set
    print(f"  그중 로고가 아닌 것(점수 숫자 등) {len(bg_non_logo)}개: " + " ".join(f"{t:02X}" for t in sorted(bg_non_logo)))

    blocked = set(spr_pt0) | bg_non_logo

    conflict = sorted(logo_set & blocked)
    print(f"\n로고 타일 ∩ 보존 대상 = {len(conflict)}개")
    for t in conflict:
        why = []
        if t in spr_pt0:
            why.append(f"스프라이트 {spr_pt0[t]}회")
        if t in bg_non_logo:
            why.append("타이틀 BG")
        print(f"  {t:02X}: 로고에서 {used[t]}칸, {', '.join(why)} — 다시 그리면 깨진다")

    safe_logo = sorted(logo_set - blocked)
    print(f"\n[A] 로고 전용 타일 {len(safe_logo)}개 — 그대로 다시 그려도 안전")
    print("  " + " ".join(f"{t:02X}" for t in safe_logo))

    never = sorted(set(range(256)) - blocked - logo_set)

    # 관측만으로는 '이번에 안 나온 그림'을 걸러내지 못한다. CHR 실바이트로 교차 검증한다.
    chr_ = (ROOT / "extracted" / "chr.bin").read_bytes()

    def blank_in_both_banks(t: int) -> bool:
        for bank in range(len(chr_) // 8192):
            off = bank * 8192 + t * 16  # PT0는 뱅크 오프셋 0
            if any(chr_[off : off + 16]):
                return False
        return True

    empty = [t for t in never if blank_in_both_banks(t)]
    drawn = [t for t in never if not blank_in_both_banks(t)]

    print(f"\n[B1] 미관측 + CHR에서도 완전히 빈 인덱스 {len(empty)}개 — 안전")
    print("  " + " ".join(f"{t:02X}" for t in empty))
    print(f"\n[B2] 미관측이지만 CHR에 그림이 들어 있는 인덱스 {len(drawn)}개 — 쓰지 않는다")
    print("  " + " ".join(f"{t:02X}" for t in drawn))
    print(
        "     이번 실행에서 안 나왔을 뿐 사망 연출·보너스·PAUSE 등에서 쓰일 수 있다.\n"
        "     (0xB6-0xBA는 PAUSE 글자다. 번역할 때 의도적으로 덮어쓴다.)"
    )
    print(
        f"\n새 로고에 쓸 수 있는 서로 다른 타일: [A] {len(safe_logo)} + [B1] {len(empty)} = "
        f"**{len(safe_logo)+len(empty)}개**"
    )


if __name__ == "__main__":
    main()
