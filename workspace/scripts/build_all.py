"""깨끗한 original/에서 dist/까지 한 번에 다시 만든다.

각 단계가 실패하면 즉시 멈춘다. 중간 산출물은 전부 재생성 가능하다.

사용법:
    python workspace/scripts/build_all.py
    python workspace/scripts/build_all.py --skip-qa      # 에뮬레이터 없이
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / "workspace" / "scripts"

LOGO_ARGS = [
    "--font", "RixInooAriDuri Regular.ttf",
    "--size", "22",
    "--grid", "시티:7:0,커넥션:6:3",
    "--cell-w", "3", "--cell-h", "3",
    "--color", "2", "--shadow", "1", "--outline", "1",
    "--emit",
]


def run(label: str, script: str, *args: str) -> None:
    print(f"\n=== {label} ===")
    cmd = [sys.executable, str(S / script), *args]
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise SystemExit(f"{label} 실패 (종료 코드 {proc.returncode})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-qa", action="store_true", help="에뮬레이터 QA를 건너뛴다")
    ap.add_argument("--date", default=None, help="배포물 날짜(YYYYMMDD). 생략하면 오늘")
    args = ap.parse_args()

    run("1. 원본 분리", "extract_rom.py")
    run("2. 무변경 왕복 검증", "build_rom.py", "--verify")
    run("3. 문자열 전수 감사", "audit_strings.py")
    run("4. 타이틀 로고 생성", "design_logo.py", *LOGO_ARGS)
    run("5. 원장 -> 패치 설정", "build_translation.py")
    run("6. 패치 ROM 빌드", "build_patch.py", "workspace/config/patch_full.json")
    run("7. 문자열 정적 확인", "preview_strings.py", "build/city_connection_kr.nes")
    if not args.skip_qa:
        run(
            "8. 에뮬레이터 QA",
            "run_qa.py",
            "build/city_connection_kr.nes",
            "--out", "work/qa/final",
            "--frames", "20000",
            "--sample-every", "200",
            "--no-input",
            "--shots", "1200:20000:1200",
            "--timeout", "600",
        )
        run("9. 대조 시트", "contact_sheet.py", "work/qa/final", "--cols", "4")
    run("10. 배포물", "make_dist.py", *(["--date", args.date] if args.date else []))

    print("\n전체 빌드 완료.")


if __name__ == "__main__":
    main()
