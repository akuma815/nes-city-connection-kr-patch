# 빌드 절차

## 단일 명령

```powershell
python .\workspace\scripts\build_all.py
```

깨끗한 `original/`에서 `dist/`까지 한 번에 다시 만든다. 중간 산출물은 전부 재생성 가능하다.

## 단계별

```powershell
# 1. 원본 -> extracted/ (header, prg, chr)
python .\workspace\scripts\extract_rom.py

# 2. 무변경 왕복 검증 (원본과 바이트 동일해야 한다)
python .\workspace\scripts\build_rom.py --verify

# 3. 화면에 찍히는 문자열 전수 감사 — 원장이 빠뜨린 게 없는지
python .\workspace\scripts\audit_strings.py

# 4. 타이틀 로고 타일 생성
python .\workspace\scripts\design_logo.py --font "RixInooAriDuri Regular.ttf" --size 22 `
  --grid "시티:7:0,커넥션:6:3" --cell-w 3 --cell-h 3 --color 2 --shadow 1 --outline 1 --emit

# 5. 번역 원장 -> 전량 패치 설정 (글리프 슬롯 자동 배정 + 예산 검사)
python .\workspace\scripts\build_translation.py

# 6. 패치 ROM 빌드 (길이 고정·원본 대조·Expected Write 검사)
python .\workspace\scripts\build_patch.py workspace/config/patch_full.json

# 7. 검증
python .\workspace\scripts\preview_strings.py build/city_connection_kr.nes     # 전 문자열 정적 확인
python .\workspace\scripts\run_qa.py build/city_connection_kr.nes --out work/qa/final `
  --frames 20000 --no-input --shots "1200:20000:1200"
python .\workspace\scripts\contact_sheet.py work/qa/final --cols 4

# 8. 배포물 (패키지 + ZIP)
python .\workspace\scripts\make_dist.py
```

## 배포물 구성

`make_dist.py`는 다른 게임(부시도 블레이드·프리니·라쿠가키)과 같은 구조를 만든다.

```text
dist/CityConnection_KR_Patch_<날짜>/
├─ CityConnection_KR_<날짜>.xdelta   ROM 차분 패치
├─ apply.cmd                         원본 .nes를 끌어다 놓으면 실행
├─ apply.ps1                         해시 확인 -> 패치 -> 결과 해시 확인
├─ README_적용방법.txt
├─ SHA256.txt                        배포 파일 무결성 목록(자기 자신 제외)
├─ release_report.json               생성·역검증 기록
└─ tools/xdelta3.exe
dist/CityConnection_KR_Patch_<날짜>.zip
```

빌드 중에 다음을 스스로 검증하고, 하나라도 실패하면 패키지를 내지 않는다.

- 만든 패치를 되적용한 결과가 빌드 ROM과 SHA-256이 같은지(역검증)
- `apply.ps1`이 **공백이 든 경로**에서 실제로 동작하고 결과 해시가 맞는지
- `apply.ps1`이 잘못된 원본을 거부하는지

`apply.ps1`은 **BOM 있는 UTF-8**로 쓴다. Windows PowerShell 5.1은 BOM이 없으면
스크립트를 시스템 ANSI로 읽어 한글 메시지가 깨진다.

## 번역을 고치려면

`workspace/text/translation/translation.json` **하나만** 고친 뒤 5~8단계를 다시 돌린다.
패치 설정(`patch_full.json`)은 생성물이므로 직접 고치지 않는다.

## 도구가 강제하는 규칙

`build_translation.py`

- **cells 길이 == length.** 문자열이 코드 사이에 박혀 있어 길이를 바꾸면 뒤 코드가 밀린다.
- **슬롯 예산.** 원문 그대로 두는 영문자가 쓰는 타일을 먼저 예약한 뒤 남는 슬롯에만 한글을 배정한다.
  예약을 빼먹으면 한글이 `JALECO` 위에 덮인다(실제로 한 번 그랬다).
- **폰트 커버리지.** Galmuri8x8에 없거나 8×8을 넘는 음절이 있으면 실패시킨다.

`build_patch.py`

- **원본 대조.** 설정의 `original`이 실제 PRG 바이트와 다르면 실패한다.
- **두 뱅크 동시 기록.** 본문 글리프는 PT1의 같은 인덱스에 뱅크 0·1 모두 쓴다.
- **보호 슬롯.** 숫자 `0x30-0x39`에는 `force` 없이 쓸 수 없고, 제어값 `0xFE`/`0xFF`에는 아예 못 쓴다.
- **Expected Write.** 마지막에 원본과 diff를 떠서 선언한 오프셋 밖 변경이 0인지 검사한다.

`audit_strings.py`

- PPUDATA에 쓰는 모든 루프를 찾아 원장이 그 주소를 덮는지 대조한다.
  `**미등록**`이 나오면 번역이 빠진 화면이 있다는 뜻이다.
