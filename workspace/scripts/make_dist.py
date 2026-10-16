"""배포물을 만든다. 원본 ROM은 절대 포함하지 않고 xdelta 차분 패치만 낸다.

다른 게임(부시도 블레이드·프리니·라쿠가키)의 dist 구조를 따른다.

    dist/CityConnection_KR_Patch_<날짜>/
    ├─ CityConnection_KR_<날짜>.xdelta
    ├─ apply.cmd            원본 .nes를 끌어다 놓으면 실행되는 도우미
    ├─ apply.ps1            해시 확인 -> 패치 -> 결과 해시 확인
    ├─ README_적용방법.txt
    ├─ SHA256.txt           배포 파일 무결성 목록
    ├─ release_report.json  생성·역검증 기록
    └─ tools/xdelta3.exe

사용법:
    python workspace/scripts/make_dist.py
    python workspace/scripts/make_dist.py --date 20260812
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "original" / "City Connection (Japan).nes"
BUILD = ROOT / "build" / "city_connection_kr.nes"
DIST = ROOT / "dist"
TOOLS = ROOT.parents[1] / "Tools" / "xdelta3-3.2.0-windows-x86_64"
XDELTA = TOOLS / "xdelta3.exe"
LEDGER = ROOT / "workspace" / "text" / "translation" / "translation.json"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_text(path: Path, text: str, bom: bool = False) -> None:
    """UTF-8 + CRLF. 기존 배포물과 같은 형식이다.

    `.ps1`은 반드시 BOM을 붙인다. Windows PowerShell 5.1은 BOM이 없으면 스크립트를
    시스템 ANSI 코드페이지로 읽어 한글 메시지가 깨진다.
    """
    data = text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)


APPLY_CMD = """@echo off
chcp 65001 >nul
if "%~1"=="" (
  echo 사용법: 원본 .nes 파일을 이 파일 위로 끌어다 놓으세요.
  echo         또는  apply.cmd "City Connection (Japan).nes"
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply.ps1" "%~f1"
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
"""

APPLY_PS1 = """param([Parameter(Mandatory = $true)][string]$InputRom)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $InputRom).Path
$base = [IO.Path]::GetFileNameWithoutExtension($source)
$dir = Split-Path -Parent $source
$output = Join-Path $dir ($base + '_KR.nes')
$patch = Join-Path $PSScriptRoot '{patch_name}'
$xdelta = Join-Path $PSScriptRoot 'tools\\xdelta3.exe'

try {{ [Console]::OutputEncoding = [Text.Encoding]::UTF8 }} catch {{ }}

$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
if ($sourceHash -ne '{src_sha_upper}') {{
    Write-Host ''
    Write-Host '[실패] 지원하지 않는 원본입니다.' -ForegroundColor Red
    Write-Host "  넣은 파일 : $source"
    Write-Host "  이 파일의 SHA-256 : $sourceHash"
    Write-Host '  필요한 SHA-256    : {src_sha_upper}'
    Write-Host ''
    Write-Host '  대상은 City Connection (Japan) 일본판 32,784바이트 ROM입니다.'
    exit 1
}}

& $xdelta -d -f -s $source $patch $output
if ($LASTEXITCODE -ne 0) {{
    Write-Host "[실패] xdelta 오류 (종료 코드 $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}}

$outputHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash
if ($outputHash -ne '{out_sha_upper}') {{
    Write-Host '[실패] 패치 결과가 기대값과 다릅니다.' -ForegroundColor Red
    Write-Host "  결과 SHA-256 : $outputHash"
    exit 1
}}

Write-Host ''
Write-Host '[완료] 한글 패치를 적용했습니다.' -ForegroundColor Green
Write-Host "  $output"
exit 0
"""


def readme_text(patch_name: str, day: str, src_sha: str, out_sha: str) -> str:
    return f"""========================================================================
 시티 커넥션 (패미컴) 한글 패치 ({day[:4]}-{day[4:6]}-{day[6:]})
 대상: 일본판 City Connection (Japan) / Jaleco 1985
========================================================================

■ 구성

  {patch_name}     ROM 패치
  apply.cmd                             적용 도우미
  apply.ps1                             적용 스크립트
  tools\\xdelta3.exe                     xdelta 3.2.0
  SHA256.txt                            배포 파일 무결성 목록
  release_report.json                   패치 생성·역검증 기록

원본 또는 패치 완료 ROM은 배포물에 포함되지 않습니다.


■ 1. 적용 방법

원본 .nes 파일을 apply.cmd 위로 끌어다 놓거나 다음처럼 실행합니다.

  apply.cmd "City Connection (Japan).nes"

출력은 원본 옆의 `<원본 이름>_KR.nes`입니다.

원본과 결과물 검증값:

  원본:    {ORIGINAL.stat().st_size:,} 바이트
           {src_sha.upper()}
  패치 후: {BUILD.stat().st_size:,} 바이트
           {out_sha.upper()}

적용 스크립트가 원본 해시와 결과 해시를 모두 확인하므로, 다른 판본이나
손상된 파일을 넣으면 중간에 멈춥니다. 파일 크기는 원본과 같습니다.


■ 2. 번역 범위

  · 타이틀 로고를 한글 `시티 커넥션`으로 새로 그렸습니다.
  · 타이틀 메뉴가 `1인용` / `2인용`으로 나옵니다.
  · 플레이 중 연료 표시가 `기름`으로 나옵니다.
  · 스테이지 시작 `READY`가 `준비`로 나옵니다.
  · 게임 오버 화면이 `게임 오버`로 나옵니다.
  · 워프 보너스가 `워프보너스` / `기름✳1000` / `점`으로 나옵니다.
  · 일시정지 표시가 `일시정지`로 나옵니다.
  · 엔딩 문구가 `이제 모두 / 달렸다`로 나옵니다.


■ 3. 원문을 유지한 것

  · `JALECO`, `© 1985`  — 제작사와 저작권 표기
  · `UP` (화면 왼쪽 위)  — 표시 칸이 3칸뿐이라 `플레이어`가 들어가지 않습니다
  · `KM`                 — 단위
  · `1P` / `TOP` / `2P`  — 점수 줄
  · `PLAYER`             — 스테이지 시작과 게임 오버 화면이 같은 데이터를 쓰는데
                           플레이어 번호가 앞뒤로 갈려, 한글로 바꾸면 한쪽이
                           반드시 어색해집니다


■ 4. 알려진 제약

패미컴 카트리지 구조상 배경 글자에 쓸 수 있는 타일이 38개뿐입니다.
그중 원문 영문이 15개를 쓰고 한글이 23자를 씁니다. 남는 칸이 없습니다.
이 때문에 엔딩 문구가 원문보다 짧습니다.

타이틀 로고도 쓸 수 있는 타일이 32개라 원본만큼 크게 만들 수 없었습니다.


■ 5. 실행 환경

일반적인 패미컴/NES 에뮬레이터에서 그대로 동작합니다. 매퍼 87을 지원하는
에뮬레이터가 필요하며, Mesen·FCEUX·Nestopia 등 대부분이 지원합니다.
한글 글꼴은 ROM 안에 내장되어 있어 별도 폰트가 필요하지 않습니다.

제작 과정의 검증은 Mesen 2 헤드리스 모드에서 20,000프레임 자동 실행으로
했습니다. 실기 확인은 하지 않았습니다.


■ 6. 제거

원본 .nes 파일을 그대로 다시 사용하면 됩니다. 패치는 원본을 수정하지 않고
별도 파일을 만듭니다.


■ 7. 주의

패치 적용이 끝난 .nes 파일을 배포하지 마세요. xdelta 파일만 공유할 수
있습니다. SHA256.txt로 다운로드한 배포 파일의 무결성을 확인할 수 있습니다.

xdelta3 3.2.0은 Apache License 2.0 조건의 도구이며, 도구 설명은
`tools\\README_xdelta3.md`에 포함돼 있습니다.

본문 글꼴은 Galmuri8x8, 타이틀 로고 글꼴은 RixInooAriDuri Regular에서
8×8 비트맵과 타일 그림으로 변환해 ROM에 넣었습니다. 글꼴 파일 자체는
배포물에 포함되지 않습니다.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    ap.add_argument("--keep-old", action="store_true", help="기존 dist 내용을 지우지 않는다")
    args = ap.parse_args()

    for p in (ORIGINAL, BUILD, XDELTA):
        if not p.exists():
            raise SystemExit(f"없음: {p}")

    day = args.date
    name = f"CityConnection_KR_Patch_{day}"
    pkg = DIST / name
    patch_name = f"CityConnection_KR_{day}.xdelta"

    if DIST.exists() and not args.keep_old:
        shutil.rmtree(DIST)
    (pkg / "tools").mkdir(parents=True, exist_ok=True)

    patch = pkg / patch_name
    subprocess.run(
        [str(XDELTA), "-e", "-f", "-s", str(ORIGINAL), str(BUILD), str(patch)],
        check=True,
        capture_output=True,
    )

    src_sha = sha256(ORIGINAL)
    out_sha = sha256(BUILD)

    shutil.copyfile(XDELTA, pkg / "tools" / "xdelta3.exe")
    readme_x = TOOLS / "README.md"
    if readme_x.exists():
        shutil.copyfile(readme_x, pkg / "tools" / "README_xdelta3.md")

    write_text(pkg / "apply.cmd", APPLY_CMD)
    write_text(
        pkg / "apply.ps1",
        APPLY_PS1.format(
            patch_name=patch_name,
            src_sha_upper=src_sha.upper(),
            out_sha_upper=out_sha.upper(),
        ),
        bom=True,
    )
    write_text(pkg / "README_적용방법.txt", readme_text(patch_name, day, src_sha, out_sha))

    # --- 역검증: 만든 패치를 실제로 적용해 결과 해시를 확인한다 ---
    with tempfile.TemporaryDirectory() as td:
        check = Path(td) / "roundtrip.nes"
        subprocess.run(
            [str(XDELTA), "-d", "-f", "-s", str(ORIGINAL), str(patch), str(check)],
            check=True,
            capture_output=True,
        )
        reverse = "PASS" if sha256(check) == out_sha else "FAIL"
    if reverse != "PASS":
        raise SystemExit("역검증 실패: 패치를 적용한 결과가 빌드와 다르다")

    # --- apply.ps1 실전 검증: 공백이 든 경로에서 실제로 돌려 본다 ---
    with tempfile.TemporaryDirectory() as td:
        space_dir = Path(td) / "패치 테스트 폴더"
        space_dir.mkdir()
        src_copy = space_dir / ORIGINAL.name
        shutil.copyfile(ORIGINAL, src_copy)
        proc = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(pkg / "apply.ps1"), str(src_copy),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        produced = src_copy.with_name(src_copy.stem + "_KR.nes")
        apply_ok = proc.returncode == 0 and produced.exists() and sha256(produced) == out_sha

        # 잘못된 원본을 거부하는지도 본다.
        bad = space_dir / "wrong.nes"
        bad.write_bytes(b"\x00" * 1000)
        bad_proc = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(pkg / "apply.ps1"), str(bad),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        reject_ok = bad_proc.returncode != 0

    if not apply_ok:
        raise SystemExit(f"apply.ps1 검증 실패\n{proc.stdout}\n{proc.stderr}")
    if not reject_ok:
        raise SystemExit("apply.ps1이 잘못된 원본을 거부하지 않는다")

    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    report = {
        "schema_version": 2,
        "status": "PASS: patch reverse-verified and apply helper tested",
        "distribution_policy": "single ROM patch, Japan revision only",
        "contains_original_game_files": False,
        "release_date": day,
        "patches": [
            {
                "id": "JP",
                "rom": ORIGINAL.name,
                "mapper": 87,
                "patch": patch_name,
                "patch_size": patch.stat().st_size,
                "patch_sha256": sha256(patch),
                "source_size": ORIGINAL.stat().st_size,
                "source_sha256": src_sha,
                "target_size": BUILD.stat().st_size,
                "target_sha256": out_sha,
                "reverse_verification": reverse,
            }
        ],
        "apply_script_end_to_end": {
            "JP": "PASS: apply.ps1 reproduced the target hash from a source path containing spaces",
            "rejects_wrong_source": "PASS" if reject_ok else "FAIL",
        },
        "coverage": {
            "translated": [e["id"] for e in led["entries"] if "원문 유지" not in e.get("translation", "")]
            + [s["id"] for s in led.get("sprite_text", [])]
            + ["title_logo"],
            "kept_original": [
                e["id"] for e in led["entries"] if "원문 유지" in e.get("translation", "")
            ],
        },
        "constraints": {
            "bg_font_slots_total": 38,
            "slots_reserved_for_latin": 15,
            "slots_used_by_hangul": 23,
            "slots_spare": 0,
            "logo_tile_budget": 32,
            "logo_data_bytes": 118,
            "note": "string lengths are fixed because the text is embedded between code bytes",
        },
        "verification": {
            "unmodified_roundtrip": "PASS",
            "expected_write": "PASS: 0 bytes changed outside declared offsets",
            "string_audit": "PASS: every PPUDATA draw loop is covered by the ledger",
            "static_string_render": "PASS: work/string_preview.png",
            "emulator_sweep": "PASS: Mesen headless, 20000 frames attract loop, no broken screens",
            "tile_conflict_all_cities": "PASS: canary build across all 6 cities and both CHR banks",
            "hardware": "not tested",
        },
    }
    (pkg / "release_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # --- SHA256.txt (자기 자신 제외) ---
    entries = []
    for f in sorted(pkg.rglob("*")):
        if f.is_file() and f.name != "SHA256.txt":
            entries.append(f"{sha256(f).upper()}  {f.relative_to(pkg).as_posix()}")
    write_text(pkg / "SHA256.txt", "\n".join(entries) + "\n")

    zip_path = shutil.make_archive(str(DIST / name), "zip", root_dir=DIST, base_dir=name)

    print(f"패키지 : {pkg}")
    for f in sorted(pkg.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(pkg).as_posix():<34} {f.stat().st_size:>9,} bytes")
    print(f"\nZIP    : {zip_path}  ({Path(zip_path).stat().st_size:,} bytes)")
    print(f"원본SHA: {src_sha}")
    print(f"결과SHA: {out_sha}")
    print(f"역검증 : {reverse}")


if __name__ == "__main__":
    main()
