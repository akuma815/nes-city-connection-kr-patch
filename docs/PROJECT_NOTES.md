# City Connection (Japan) 한글화

- 플랫폼 / 지역 / 리비전: Famicom(NES) / 일본 / Jaleco 1985
- 지원 원본 파일명·크기·SHA-256:
  - `City Connection (Japan).nes`
  - 32,784 bytes
  - `6476d10be301a331904bb42db0bd9811d13ff4ba991c32611b7c746d3560f61f`
- 현재 단계: **전량 번역 완료 / 배포물 생성 완료** (실기 QA 미실시)
- 원본 위치와 수정 금지 규칙: `original/`은 읽기 전용이다. 산출물은 `build/`, `work/`, `dist/`에만 만든다.
- 번역 원장(SSOT): [workspace/text/translation/translation.json](workspace/text/translation/translation.json)
- 단일 빌드 명령: `python .\workspace\scripts\build_all.py`
- 빌드 출력: `build/city_connection_kr.nes` — SHA-256 `03f0de5a1bac876873cdbae143d84980f99154bb9b796b2db4edbd5e6079fca4`
- 배포물: `dist/CityConnection_KR_Patch_20260812.zip` — `apply.cmd`로 원본 .nes를 끌어다 놓으면 적용된다
- 에뮬레이터: Mesen 2 (`H:\Mesen`), 헤드리스 테스트 러너로 자동 QA
- 폰트: 본문 `Font/Galmuri8x8.ttf` @16ppem, 로고 `Font/RixInooAriDuri Regular.ttf` @22px

## 번역 결과

| 화면 | 원문 | 번역 |
| --- | --- | --- |
| 타이틀 로고 | `City CONNECTION` | **`시티 커넥션`** (새로 그림) |
| 타이틀 메뉴 | `1PLAYER` / `2PLAYERS` | `1인용` / `2인용` |
| HUD | `OIL` | `기름` |
| 스테이지 시작 | `READY` | `준비` |
| 게임 오버 | `GAME OVER` | `게임 오버` |
| 보너스 | `WARP BONUS` / `OIL✳1000` / `POINT` | `워프보너스` / `기름✳1000` / `점` |
| 일시정지 | `PAUSE` | `일시정지` |
| 엔딩 | `NOW,YOU HAVE DRIVEN ALL THE HIGHWAY!!` | `이제 모두 / 달렸다` |

원문 유지: `JALECO`, `© 1985`, `UP`, `KM`, `1P`/`TOP`/`2P`, ` PLAYER` — 이유는 [docs/decisions.md](docs/decisions.md) D-009.

## 검증 상태

| | 결과 |
| --- | --- |
| 무변경 왕복 | **PASS** — 재접합 ROM이 원본과 바이트 동일 |
| Expected Write | **PASS** — 선언 오프셋 밖 변경 0바이트 |
| 문자열 전수 감사 | **PASS** — PPUDATA 루프 전부 원장이 커버 |
| 전 문자열 정적 렌더 | **PASS** — `work/string_preview.png` |
| 에뮬레이터 20,000프레임 스윕 | **PASS** — 깨진 화면 없음 |
| 6개 도시 타일 충돌 | **PASS** — 카나리아로 전 도시 검증 |
| xdelta 왕복 | **PASS** — 패치 적용 결과가 빌드와 SHA 일치 |
| 실기 / 다른 에뮬레이터 | **미실시** |

## 핵심 제약 (다시 손댈 때 반드시 읽을 것)

- **문자열 길이를 바꿀 수 없다.** 코드 사이에 데이터로 박혀 있다. 남는 칸은 `0x40` 공백으로 채운다.
- **한글 글리프 슬롯은 38개.** 원문 영문 1자를 남길 때마다 한글 1자를 못 쓴다. 현재 한글 23자 / 여유 0.
- **타이틀 메뉴는 스프라이트**라 한 줄이 정확히 8칸이고 X좌표가 고정이다.
- **HUD 정적 라벨은 3칸**뿐이다. 나머지는 동적 필드가 덮어쓴다.
- **타이틀 로고 타일은 32개**가 상한이고 데이터는 118바이트 고정이다.

## 폴더 매핑

루트의 `신규_게임_한글화_구조_가이드.md` 4장 표준 구조를 따른다.

| 폴더 | 내용 |
| --- | --- |
| `original/` | 원본 ROM (수정 금지) |
| `extracted/` | `header.bin` / `prg.bin` / `chr.bin` / `rom_info.json` |
| `workspace/text/translation/` | **번역 원장(SSOT). 사람이 고치는 유일한 파일** |
| `workspace/config/` | ROM 상수(`rom_map.json`)와 패치 정의. `patch_full.json`은 생성물 |
| `workspace/scripts/` | 조사·폰트·로고·빌드·QA 스크립트 |
| `workspace/tests/` | Mesen QA 스크립트 템플릿 |
| `work/` | 언제든 지우고 다시 만드는 미리보기·QA 출력 |
| `build/` | 패치 ROM |
| `dist/` | 배포 패키지와 ZIP. `apply.cmd` / `apply.ps1` / `README_적용방법.txt` / `SHA256.txt` / `release_report.json` / `tools\xdelta3.exe` |

## 스크립트

| 스크립트 | 역할 |
| --- | --- |
| `build_all.py` | **단일 진입점.** original → dist 전 과정 |
| `extract_rom.py` / `build_rom.py` | 분리 / 재접합·무변경 검증 |
| `make_glyphs.py` | Galmuri8x8 → NES 2bpp 8×8 글리프, 커버리지 검사 |
| `design_logo.py` | 타이틀 로고 설계(격자 정렬·타일 병합·테두리·그림자) |
| `build_translation.py` | 원장 → 패치 설정. 슬롯 배정·예산·길이 검사 |
| `build_patch.py` | 설정 → 패치 ROM. 원본 대조·Expected Write |
| `audit_strings.py` | 화면 문자열 전수 감사(번역 누락 탐지) |
| `preview_strings.py` | 패치 ROM의 전 문자열 정적 렌더 |
| `run_qa.py` / `contact_sheet.py` | Mesen 헤드리스 실행 / 대조 시트 |
| `analyze_tile_usage.py` / `analyze_logo.py` | 타일 회수 가능 여부 판정 |
| `make_dist.py` | xdelta 패치·해시·설명서 생성 |
| `chr_to_png.py` / `render_pattern_table.py` / `render_screen.py` / `hexdump.py` / `survey_*.py` | 조사 도구 |

## 다음 할 일

1. 실기 또는 다른 에뮬레이터 교차 확인
2. 엔딩·보너스·일시정지 화면을 실제 플레이로 도달해 확인 (현재는 정적 렌더로만 확인)
3. 배포 전 폰트 라이선스 최종 확인
