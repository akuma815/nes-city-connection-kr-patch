"""QA 실행들의 bg_tile_usage.txt를 합쳐 폰트 영역 타일의 회수 가능 여부를 판정한다.

판정 기준 세 가지를 분리한다.

1. PT0(`$0000`)과 PT1(`$1000`)은 **서로 다른 CHR 4KB 영역**이다. 같은 인덱스라도 다른 그림이므로
   PT1 폰트 슬롯의 회수 가능 여부는 PT1 관측치로만 판정한다. PT0 쪽 사용량은 참고로만 보인다.
2. PT1에서 관측된 사용이라도 **우리가 교체할 문자열이 쓴 것**이면 회수해도 된다.
   원문에 실제로 등장하는 문자는 rom_map.json의 strings에서 계산한다.
3. 배경(도시·하늘·게이지)이 쓰는 타일은 회수하면 화면이 깨진다.

**원본 ROM 실행 결과만 입력해야 한다.** 패치 빌드(PoC·카나리아) 결과를 섞으면
우리가 넣은 글리프 사용량이 배경 사용으로 잘못 집계된다.

관측되지 않았다는 것은 '이번 실행 범위에서 안 쓰였다'는 뜻이지 '절대 안 쓰인다'가 아니다.

사용법:
    python workspace/scripts/analyze_tile_usage.py work/qa/attract work/qa/play
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROM_MAP = ROOT / "workspace" / "config" / "rom_map.json"

FONT_RANGE = range(0x28, 0x60)

# survey.md 4장에서 확인한 폰트 배치.
LABEL = {}
for t in range(0x28, 0x2D):
    LABEL[t] = "빈 타일"
LABEL.update({0x2D: "','", 0x2E: "'*'", 0x2F: "'!'"})
for t in range(0x30, 0x3A):
    LABEL[t] = f"'{t - 0x30}'"
LABEL.update({0x3A: "블록", 0x3B: "블록", 0x3C: "블록", 0x3D: "블록", 0x3E: "블록", 0x3F: "빈 타일"})
LABEL[0x40] = "공백"
for t in range(0x41, 0x5B):
    LABEL[t] = f"'{chr(t)}'"
LABEL.update({0x5B: "'-'", 0x5C: "'.'", 0x5D: "'='", 0x5E: "'(c)'", 0x5F: "기호"})

PROTECTED = set(range(0x30, 0x3A))  # 숫자는 점수·거리·연도에 필요
# 배경 그림·게이지·하늘로 확인된 슬롯. 문자열과 무관하므로 회수 대상이 아니다.
BACKGROUND_SLOTS = {0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F, 0x40}

def text_tiles() -> tuple[set[int], list[str]]:
    """원문 문자열이 실제로 쓰는 타일 인덱스를 PRG 실바이트에서 읽는다.

    전사에 기대면 공백·기호를 한 칸 놓치는 순간 판정이 뒤집힌다. addr+length로 직접 읽는다.
    """
    cfg = json.loads(ROM_MAP.read_text(encoding="utf-8"))
    prg = (ROOT / "extracted" / "prg.bin").read_bytes()
    used: set[int] = set()
    detail = []
    for s in cfg.get("strings", []):
        if "length" not in s:  # 타이틀 로고 타일맵처럼 문자열이 아닌 항목
            continue
        addr = int(s["addr"], 16)
        off = addr - (0xC000 if addr >= 0xC000 else 0x8000)
        raw = prg[off : off + s["length"]]
        used.update(raw)
        detail.append(f"{s['id']:<18} ${addr:04X} +{s['length']:<3} {raw.hex(' ')}")
    # 제어값은 타일이 아니다.
    used -= {0xFE, 0xFF}
    return used, detail


def parse(path: Path) -> dict[int, dict[int, int]]:
    """{패턴테이블주소: {타일: 횟수}}"""
    out: dict[int, dict[int, int]] = defaultdict(dict)
    pt = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#\s*backgroundPatternAddr=\$([0-9A-Fa-f]+)", line)
        if m:
            pt = int(m.group(1), 16)
            continue
        m = re.match(r"([0-9A-Fa-f]{2})\s+(\d+)", line)
        if m and pt is not None:
            out[pt][int(m.group(1), 16)] = out[pt].get(int(m.group(1), 16), 0) + int(m.group(2))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="run_qa.py 출력 폴더들")
    args = ap.parse_args()

    merged: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    sources = []
    for r in args.runs:
        p = ROOT / r / "bg_tile_usage.txt"
        if not p.exists():
            print(f"건너뜀(없음): {p}")
            continue
        sources.append(r)
        for pt, bucket in parse(p).items():
            for tile, n in bucket.items():
                merged[pt][tile] += n

    print(f"합친 실행: {', '.join(sources)}\n")
    pt0 = merged.get(0x0000, {})
    pt1 = merged.get(0x1000, {})

    text, detail = text_tiles()
    cfg = json.loads(ROM_MAP.read_text(encoding="utf-8"))
    budget = cfg.get("glyph_budget", {})
    canary_ok = {int(x, 16) for x in budget.get("canary_verified", [])}
    if canary_ok:
        print(f"카나리아 검증 완료 슬롯 {len(canary_ok)}개 — 근거: {budget.get('canary_evidence','')}\n")

    print("원문 문자열(PRG 실바이트):")
    for line in detail:
        print("  " + line)
    print()

    print(f"{'타일':>5} {'내용':<6} {'PT1사용':>9} {'(참고)PT0':>10}  판정")
    print("-" * 70)
    reclaim_now, reclaim_unobserved, blocked = [], [], []
    for t in FONT_RANGE:
        a, b = pt1.get(t, 0), pt0.get(t, 0)
        if t in PROTECTED:
            verdict = "회수 금지 — 숫자"
            blocked.append(t)
        elif t in BACKGROUND_SLOTS:
            verdict = f"회수 금지 — 배경/게이지 ({a}회)"
            blocked.append(t)
        elif t in text:
            verdict = "회수 가능 — 원문 문자열 전용"
            reclaim_now.append(t)
        elif a:
            verdict = f"회수 불가 — 문자열 밖 사용 {a}회"
            blocked.append(t)
        elif t in canary_ok:
            verdict = "회수 가능 — 카나리아 전 도시 검증"
            reclaim_now.append(t)
        else:
            verdict = "회수 후보 — 미관측"
            reclaim_unobserved.append(t)
        print(f"  {t:02X}  {LABEL.get(t,''):<6} {a:>9} {b:>10}  {verdict}")

    print(f"\n[확정] 회수 가능 슬롯 {len(reclaim_now)}개 — 원문 문자열 전용이거나 카나리아로 검증됨")
    print("  " + " ".join(f"{t:02X}" for t in sorted(reclaim_now)))
    if reclaim_unobserved:
        print(f"\n[후보] 아직 근거가 미관측뿐인 슬롯 {len(reclaim_unobserved)}개 — 카나리아로 확인 후 사용")
        print("  " + " ".join(f"{t:02X}" for t in sorted(reclaim_unobserved)))
    print(f"\n한글 글리프 예산: 확정 {len(reclaim_now)}자, 후보 포함 최대 {len(reclaim_now)+len(reclaim_unobserved)}자")
    print(
        "\n주의\n"
        "  - 이 판정은 실행한 구간에서만 유효하다. 뒤 스테이지(도시)는 다른 타일 인덱스를\n"
        "    쓸 수 있으므로 커버리지를 넓힌 뒤 다시 돌린다.\n"
        "  - PT0 열은 참고값이다. PT0는 별도 CHR 영역이라 PT1 슬롯 회수와 무관하다."
    )


if __name__ == "__main__":
    main()
