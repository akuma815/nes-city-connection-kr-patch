"""Mesen 헤드리스 테스트 러너로 ROM을 돌리고 스크린샷·타일 사용 보고서를 모은다.

Mesen은 GUI 앱이지만 `--testRunner <lua> <rom>`으로 헤드리스 실행을 지원한다.
스크립트에서 파일을 쓰려면 Mesen 설정의 Debug > ScriptWindow > AllowIoOsAccess가 켜져 있어야 한다.

사용법:
    python workspace/scripts/run_qa.py build/poc_ready.nes --out work/qa/poc
    python workspace/scripts/run_qa.py build/canary_tiles.nes --out work/qa/canary --frames 3600
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "workspace" / "tests" / "qa_capture.lua.tmpl"
DEFAULT_MESEN = Path(r"H:\Mesen\Mesen.exe")

# 타이틀 -> 1인용 시작 -> 첫 스테이지까지 끌고 가는 최소 시나리오.
# 프레임 수는 NTSC 60fps 기준이다.
DEFAULT_PRESSES = [
    {"from": 300, "to": 310, "button": "start"},   # 타이틀에서 1PLAYER 선택
    {"from": 400, "to": 405, "button": "start"},   # 혹시 남은 확인 단계
]
DEFAULT_SHOTS = {
    240: "01_title",
    330: "02_after_start",
    380: "03_stage_start",
    420: "04_stage_start_b",
    480: "05_play",
    600: "06_play",
    900: "07_play",
    1500: "08_play",
}


def lua_table(obj) -> str:
    if isinstance(obj, dict):
        items = ", ".join(f"[{lua_table(k)}]={lua_table(v)}" for k, v in obj.items())
        return "{" + items + "}"
    if isinstance(obj, list):
        return "{" + ", ".join(lua_table(v) for v in obj) + "}"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, str):
        return '"' + obj.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(obj)


def lua_press_table(presses: list[dict]) -> str:
    parts = [
        "{from=%d, to=%d, button=%s}" % (p["from"], p["to"], lua_table(p["button"]))
        for p in presses
    ]
    return "{" + ", ".join(parts) + "}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", help="프로젝트 루트 기준 ROM 경로")
    ap.add_argument("--out", default="work/qa/run")
    ap.add_argument("--frames", type=int, default=1800)
    ap.add_argument("--sample-every", type=int, default=10)
    ap.add_argument("--mesen", default=str(DEFAULT_MESEN))
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument(
        "--shots",
        help="기본 촬영 계획 대신 쓸 프레임 목록. '600,700,800' 또는 '600:900:20'(from:to:step)",
    )
    ap.add_argument("--no-input", action="store_true", help="입력 없이 어트랙트 모드만 돌린다")
    ap.add_argument(
        "--press-start-every",
        type=int,
        default=0,
        help="N프레임마다 Start를 8프레임 누른다. 게임 오버 후 재시작으로 커버리지를 넓힐 때 쓴다",
    )
    ap.add_argument(
        "--poke",
        action="append",
        default=[],
        metavar="ADDR=VAL",
        help="매 프레임 시작 시 RAM에 강제 기록. 예: --poke A0=3 (스테이지 인덱스). 여러 번 지정 가능",
    )
    args = ap.parse_args()

    mesen = Path(args.mesen)
    if not mesen.exists():
        raise SystemExit(f"Mesen.exe를 찾을 수 없다: {mesen}")

    rom = ROOT / args.rom
    if not rom.exists():
        raise SystemExit(f"ROM 없음: {rom}")

    out = ROOT / args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    if args.shots:
        if ":" in args.shots:
            a, b, step = (int(x) for x in args.shots.split(":"))
            frames_list = list(range(a, b + 1, step))
        else:
            frames_list = [int(x) for x in args.shots.split(",")]
        shots = {f: f"f{f:05d}" for f in frames_list if f <= args.frames}
    else:
        shots = {f: n for f, n in DEFAULT_SHOTS.items() if f <= args.frames}

    if args.no_input:
        presses: list[dict] = []
    else:
        presses = list(DEFAULT_PRESSES)
    if args.press_start_every:
        for f in range(args.press_start_every, args.frames, args.press_start_every):
            presses.append({"from": f, "to": f + 8, "button": "start"})

    pokes = []
    for spec in args.poke:
        addr_s, _, val_s = spec.partition("=")
        pokes.append({"addr": int(addr_s, 16), "value": int(val_s, 0)})
    script = (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("@@OUT@@", str(out).replace("\\", "/"))
        .replace("@@SHOTS@@", lua_table(shots))
        .replace("@@PRESSES@@", lua_press_table(presses))
        .replace("@@LAST_FRAME@@", str(args.frames))
        .replace("@@NT_SAMPLE_EVERY@@", str(args.sample_every))
        .replace(
            "@@POKES@@",
            "{" + ", ".join("{addr=%d, value=%d}" % (p["addr"], p["value"]) for p in pokes) + "}",
        )
    )
    script_path = out / "qa_capture.lua"
    script_path.write_text(script, encoding="utf-8")

    # Mesen은 경로에 공백이 있으면 인자 분해에 민감하다. 실행 전 공백 없는 곳으로 복사한다.
    staged_rom = out / "rom.nes"
    shutil.copyfile(rom, staged_rom)

    cmd = [str(mesen), "--testRunner", str(script_path), str(staged_rom)]
    print("실행:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    try:
        proc = subprocess.run(
            cmd, cwd=str(mesen.parent), capture_output=True, text=True, timeout=args.timeout
        )
        print(f"종료 코드: {proc.returncode}")
    except subprocess.TimeoutExpired:
        print(f"{args.timeout}초 안에 종료되지 않았다. Lua 오류로 스크립트가 죽었을 수 있다.")

    log = out / "qa_log.txt"
    if log.exists():
        print("\n--- qa_log.txt ---")
        print(log.read_text(encoding="utf-8"))
    else:
        print("\nqa_log.txt가 없다. Lua 스크립트가 실행되지 않았다.")
        if proc.stdout:
            print(proc.stdout[-2000:])
        sys.exit(1)

    pngs = sorted(out.glob("*.png"))
    print(f"스크린샷 {len(pngs)}장: {', '.join(p.name for p in pngs)}")
    print(f"출력 폴더: {out}")


if __name__ == "__main__":
    main()
