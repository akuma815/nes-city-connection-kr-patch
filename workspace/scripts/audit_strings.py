"""PRG에서 화면에 찍힐 수 있는 문자열 후보를 전수 감사한다.

`LDA abs,X` / `LDA abs,Y`로 읽어 `$2007`(PPUDATA)에 쓰는 루프를 찾아
원장(`translation.json`)이 그 주소를 덮고 있는지 대조한다.

QA에서 `$8B48`의 " PLAYER"를 놓쳤던 것 같은 누락을 기계적으로 잡기 위한 도구다.

사용법:
    python workspace/scripts/audit_strings.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRG = (ROOT / "extracted" / "prg.bin").read_bytes()
LEDGER = ROOT / "workspace" / "text" / "translation" / "translation.json"
B = 0x8000

FONT_RANGE = set(range(0x28, 0x60))


def covered() -> list[tuple[int, int, str]]:
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    out = []
    for e in led["entries"]:
        addr = int(e["addr"], 16)
        addr = addr - (0xC000 if addr >= 0xC000 else 0x8000) + 0x8000
        out.append((addr, addr + e["length"] - 1, e["id"]))
    # 타이틀 로고는 문자열이 아니라 타일맵이라 원장이 아니라 patch_logo.json이 덮는다.
    # 엔딩($8E0A)은 이 블록과 같은 베이스($8D94)에서 X=0x76으로 이어 읽는다.
    out.append((0x8D94, 0x8E09, "title_logo(patch_logo.json)"))
    return out


def main() -> None:
    cov = covered()
    print("원장이 덮는 범위")
    for a, b, i in sorted(cov):
        print(f"  ${a:04X}-${b:04X}  {i}")

    print("\n=== LDA abs,X/Y -> STA $2007 패턴 ===")
    found = []
    for i in range(len(PRG) - 8):
        if PRG[i] not in (0xBD, 0xB9):
            continue
        target = PRG[i + 1] | (PRG[i + 2] << 8)
        # 가까운 뒤쪽에 STA $2007이 있으면 화면에 찍는 루프다.
        # 바로 뒤가 아닐 수 있다. 엔딩·로고처럼 0xFE/0xFF를 먼저 비교하는 형태가 있다.
        window = PRG[i + 3 : i + 20]
        if b"\x8d\x07\x20" not in window:
            continue
        # 루프 길이: 뒤쪽의 CPX/CPY #imm. 종료자 방식이면 없다.
        count = None
        for j in range(i + 3, min(i + 20, len(PRG) - 1)):
            if PRG[j] in (0xE0, 0xC0) and PRG[j + 1] not in (0xFE, 0xFF):
                count = PRG[j + 1]
                break
        terminator = b"\xc9\xff" in window or b"\xc9\xfe" in window
        found.append((i, target, count, terminator))

    for i, target, count, terminator in found:
        off = target - (0xC000 if target >= 0xC000 else 0x8000)
        if terminator and count is None:
            n = 0
            while off + n < len(PRG) and PRG[off + n] != 0xFF and n < 200:
                n += 1
            n += 1
        else:
            n = count if count else 8
        data = PRG[off : off + n]
        printable = "".join(
            chr(b) if 0x30 <= b <= 0x5F else ("_" if b == 0x40 else ".") for b in data
        )
        hit = [x for x in cov if x[0] <= target <= x[1]]
        # 폰트 범위 밖 바이트가 많으면 텍스트가 아니라 좌표·인덱스 데이터다.
        text_like = sum(1 for b in data if b in FONT_RANGE) >= max(2, n // 2)
        mark = f"원장:{hit[0][2]}" if hit else ("**미등록**" if text_like else "데이터로 보임")
        kind = "종료자" if terminator else f"{count if count is not None else '?'}칸"
        print(
            f"  ${B+i:04X}  LDA ${target:04X},{'X' if PRG[i]==0xBD else 'Y'}  "
            f"{kind:>6}  [{printable[:60]}]  {mark}"
        )

    print(
        "\n주의: count는 바로 뒤의 CPX/CPY 즉시값이다. 여러 구간을 이어 그리는 블록"
        "(보너스처럼)은 누적값이라 실제 구간 길이와 다를 수 있다."
    )


if __name__ == "__main__":
    main()
