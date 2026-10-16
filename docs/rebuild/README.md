# 시티 커넥션 최종판 재빌드

Git 소스와 별도로 준비한 지원 일본판 원본 ROM만으로 2026-08-12 최종 배포본을 다시 만듭니다. 개인 복원 ZIP이나 예전 추출·작업·검증 폴더는 필요하지 않습니다.

## 실행

Python 3.12 환경에서 저장소 최상위에서 실행합니다.

```powershell
python -m pip install -r requirements-rebuild.txt
python -X utf8 -B scripts/rebuild_final.py --source-rom "일본판 원본의 절대 경로.nes" --output-dir build/restored_final
```

출력 폴더는 아직 존재하지 않는 새 경로를 사용합니다. 원본은 수정하지 않습니다. 출력 폴더의 `project/build/city_connection_kr.nes`가 결과 ROM이며, `REBUILD_RESULT.json`에 최종 해시와 검증 결과를 기록합니다.

| 구분 | SHA-256 |
| --- | --- |
| 지원 원본, 32,784바이트 | `6476d10be301a331904bb42db0bd9811d13ff4ba991c32611b7c746d3560f61f` |
| 최종 ROM, 32,784바이트 | `03f0de5a1bac876873cdbae143d84980f99154bb9b796b2db4edbd5e6079fca4` |

## 재현 방식

필수 입력 4개의 해시를 [INPUTS.json](INPUTS.json)에 고정했습니다. 번역 원장·ROM 맵·승인 로고 설정은 기존 Git 소스와 동일하며, 누락된 Galmuri8x8 폰트를 라이선스와 함께 보완했습니다. 로고는 `workspace/config/patch_logo.json`의 승인된 32개 타일 비트맵과 타일맵에서 재현하므로 Rix 원본 폰트 없이 최종 배포본을 만들 수 있습니다.

새 출력 폴더에 작업용 소스와 입력을 복제한 뒤 원본 분리 → 무변경 재조립 → 문자열 감사 → 원장 재삽입 설정 생성 → 패치 ROM 빌드 → 정적 문자열 미리보기를 실행합니다. 원래 체크아웃의 설정·원장은 덮어쓰지 않습니다. 생성된 설정과 ROM은 출력 폴더 안에만 둡니다. 이 명령은 에뮬레이터나 xdelta3를 호출하지 않습니다.

실제 빌드 및 공개 릴리즈의 `apply.ps1` 적용 검증은 [VERIFICATION_2026-10-16.json](VERIFICATION_2026-10-16.json)을 참고하세요. 정적 미리보기는 게임 실행 화면이나 플레이 검수가 아닙니다. 이번 작업에서 새로운 에뮬레이터 실행·전체 플레이·실기 검증은 수행하지 않았습니다.

## 편집을 이어갈 때

동결된 최종판 재현 명령은 입력 변경을 거부합니다. 새 번역은 `workspace/text/translation/translation.json`에서 수정하고 기존 `build_translation.py`·`build_patch.py`를 새 작업 공간에서 사용하세요. 로고를 다시 디자인하려면 기존 `design_logo.py`에 별도 보유한 Rix 폰트의 절대 경로를 넘겨 새 `patch_logo.json`을 생성합니다. 최종판 복원에는 이 과정이 필요하지 않습니다. 기존 `build_all.py`는 로고 생성·에뮬레이터 QA·배포 포장까지 포함하는 개발용 경로라 별도 폰트·Mesen·xdelta3 준비가 필요합니다.

원본 ROM·BIOS·출력 ROM은 Git에 올리지 않습니다. 과거 세이브·중간 버전·실행 덤프 전체는 공개 범위에 포함하지 않습니다.
