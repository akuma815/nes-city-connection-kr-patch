"""PRG-ROM의 빈 공간 후보와 CHR 뱅크 전환 코드를 찾는다.

- 같은 바이트가 16회 이상 반복되는 구간(패딩 후보)
- $6000-$7FFF 스토어 명령(매퍼 87 CHR 뱅크 선택 후보)
- 리셋/NMI/IRQ 벡터

사용법:
    python workspace/scripts/survey_prg.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRG = (ROOT / "extracted" / "prg.bin").read_bytes()
BASE = 0xC000  # 16KB PRG는 $C000-$FFFF에 매핑되고 $8000-$BFFF에 미러된다.


def filler_runs(min_len: int = 16) -> None:
    print(f"--- {min_len}바이트 이상 동일 바이트 반복(빈 공간 후보) ---")
    total = 0
    i = 0
    n = len(PRG)
    while i < n:
        j = i
        while j + 1 < n and PRG[j + 1] == PRG[i]:
            j += 1
        run = j - i + 1
        if run >= min_len:
            print(f"  {BASE+i:04X}-{BASE+j:04X}  {run:5d} bytes  value=0x{PRG[i]:02X}")
            total += run
        i = j + 1
    print(f"  합계 {total} bytes / {n} bytes ({total*100/n:.1f}%)")


def bank_writes() -> None:
    print("--- $6000-$7FFF 스토어(매퍼 87 CHR 뱅크 선택 후보) ---")
    # 8D = STA abs, 8E = STX abs, 8C = STY abs, 9D = STA abs,X, 99 = STA abs,Y
    ops = {0x8D: "STA", 0x8E: "STX", 0x8C: "STY", 0x9D: "STA ,X", 0x99: "STA ,Y"}
    hits = 0
    for i in range(len(PRG) - 2):
        op = PRG[i]
        if op in ops:
            addr = PRG[i + 1] | (PRG[i + 2] << 8)
            if 0x6000 <= addr <= 0x7FFF:
                ctx = " ".join(f"{b:02X}" for b in PRG[max(0, i - 4) : i + 3])
                print(f"  {BASE+i:04X}  {ops[op]} ${addr:04X}   [{ctx}]")
                hits += 1
    if not hits:
        print("  없음")


def vectors() -> None:
    nmi = PRG[-6] | (PRG[-5] << 8)
    rst = PRG[-4] | (PRG[-3] << 8)
    irq = PRG[-2] | (PRG[-1] << 8)
    print(f"--- 벡터 --- NMI=${nmi:04X} RESET=${rst:04X} IRQ=${irq:04X}")


if __name__ == "__main__":
    vectors()
    bank_writes()
    filler_runs()
