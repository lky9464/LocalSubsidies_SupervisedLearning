# 오프라인 사용법

인터넷이 없는 PC에서 이 프로젝트를 설치·실행하는 순서입니다.  
GitHub에서 **파일 2개**를 받아 USB 등으로 옮긴 뒤, 아래 순서대로 진행하면 됩니다.

> **한 줄 요약**  
> 소스 ZIP + Release의 `wheels-win-amd64-py312.zip` → Python 3.12 설치 → `SetupOffline.bat` → `data_root`·raw 준비 → `RunWeb.bat`

---

## 0. 지원 환경 · 미리 알아둘 것

| 항목 | 내용 |
|------|------|
| OS | Windows 10 / 11 **64-bit** |
| Python | **3.12** x64 (wheel 묶음 기준) |
| 네트워크 | **설치·실행 시 인터넷 불필요** (wheel을 미리 받아 둔 경우) |
| 데이터 | raw CSV는 GitHub에 **없음** — 사용자가 `{data_root}`에 직접 둠 |

이 저장소에는 **코드·문서·스키마**만 있습니다.  
학습·추론용 CSV, 모델, 행단위 점수는 Release에도 포함되지 않습니다.

---

## 1. (온라인 PC) GitHub에서 받을 것 — 2개

온라인 가능한 PC에서 아래를 받아 USB·외장하드 등에 복사합니다.

### ① 소스 코드 (ZIP)

1. 저장소 열기:  
   https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
2. 초록색 **Code** 버튼 → **Download ZIP**  
3. 받은 파일 예: `LocalSubsidies_SupervisedLearning-main.zip`

### ② wheel 묶음 (패키지 설치용)

1. **Releases** 열기:  
   https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases  
2. 태그 **v0.2.0** (또는 최신 버전) 선택  
3. Assets에서 **`wheels-win-amd64-py312.zip`** 다운로드  
   - 직접 링크 예:  
     https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.2.0

### (권장) Python 설치 파일도 함께

오프라인 PC에 Python이 없으면, 온라인 PC에서 미리 받아 둡니다.

- Python 3.12 Windows **64-bit** installer  
  https://www.python.org/downloads/windows/  
  (`Windows installer (64-bit)` — 파일명에 `amd64` 포함)
- (선택) [VC++ Redistributable x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)  
  — numpy / catboost 실행 오류 시 필요

### USB에 넣을 목록 (체크)

- [ ] `LocalSubsidies_SupervisedLearning-main.zip` (소스)
- [ ] `wheels-win-amd64-py312.zip` (패키지)
- [ ] Python 3.12 x64 설치 파일 (필요 시)
- [ ] 학습·평가용 raw CSV (사용자 확보)
- [ ] 추론용 raw CSV (사용할 경우)

---

## 2. (오프라인 PC) 폴더 준비

### 2-1. 소스 압축 해제

원하는 경로에 풉니다. 예:

```text
C:\work\LocalSubsidies_SupervisedLearning\
```

풀린 폴더 안에 `SetupOffline.bat`, `RunWeb.bat`, `app\` 등이 보이면 됩니다.

### 2-2. wheel을 올바른 위치에 풀기

`wheels-win-amd64-py312.zip`을 열어 **안의 `.whl` 파일들**이 아래처럼 오게 합니다.

```text
LocalSubsidies_SupervisedLearning\
├── SetupOffline.bat
├── RunWeb.bat
├── InitDataRoot.bat
├── requirements.lock.txt
└── vendor\
    └── wheels\
        ├── numpy-....whl
        ├── streamlit-....whl
        ├── catboost-....whl
        └── ... (수십 개)
```

**주의:** zip 안에 `wheels` 폴더가 한 겹 더 있으면,  
`vendor\wheels\wheels\*.whl` 이 되지 않도록 **`.whl`이 바로 `vendor\wheels\` 아래** 있게 옮기세요.

### 2-3. Python 3.12 설치

1. USB의 Python 설치 파일 실행  
2. **Add python.exe to PATH** 체크 권장  
3. 설치 후 새 명령 프롬프트에서 확인:

```text
py -3.12 --version
```

`Python 3.12.x` 가 나오면 됩니다.

---

## 3. (오프라인 PC) 프로그램 설치 — 1회

프로젝트 루트에서 **`SetupOffline.bat`** 을 더블클릭합니다.

하는 일:

1. `.venv` 가상환경 생성  
2. `vendor\wheels`의 패키지를 인터넷 없이 설치  
3. `configs\local.yaml`이 없으면 예제에서 복사  

끝나면 콘솔에 **설치 완료**가 표시됩니다.  
오류가 나면 아래 [문제 해결](#6-문제-해결)을 보세요.

---

## 4. 데이터 경로 · raw 배치

### 4-1. `data_root` 설정

```text
notepad configs\local.yaml
```

예시 (프로젝트와 **형제** 폴더 권장):

```yaml
data_root: "C:/work/LocalSubsidies_ML_Data"
```

- 경로의 `\` 대신 `/` 를 써도 됩니다.  
- 실제 폴더가 아직 없어도 됩니다 → 다음 단계에서 만듭니다.

### 4-2. 폴더 골격 만들기

프로젝트 루트에서 **`InitDataRoot.bat`** 더블클릭  
(`local.yaml`의 `data_root`를 읽어 하위 폴더를 생성합니다.)

또는 경로를 직접 지정:

```text
InitDataRoot.bat "C:\work\LocalSubsidies_ML_Data"
```

### 4-3. raw CSV 넣기

| 용도 | 넣는 위치 |
|------|-----------|
| 학습·평가 | `{data_root}\raw\` |
| 추론 (라벨 미지) | `{data_root}\raw_inference\` |

컬럼 스키마는 프로젝트 루트의 [`TLS4902R_Layout.csv`](../TLS4902R_Layout.csv)를 따릅니다.  
(원본 CSV는 보통 EUC-KR 등입니다.)

---

## 5. 실행 (일상)

1. **`RunWeb.bat`** 더블클릭  
2. 브라우저에서 `http://127.0.0.1:8501`  
   (자동으로 안 열리면 주소창에 직접 입력)  
3. **검은 콘솔 창을 닫지 마세요** — 닫으면 웹 서버가 종료됩니다.

웹 UI에서 데이터 등록 · 학습 파이프라인 · 추론 등을 사용할 수 있습니다.  
메뉴 설명: [`user_guide.md`](user_guide.md) · [`web_local.md`](web_local.md)

이후 재실행은 **`RunWeb.bat`만** 다시 누르면 됩니다.  
(`SetupOffline.bat`은 패키지/환경이 바뀌었을 때만 재실행)

---

## 6. 문제 해결

| 증상 | 확인할 것 |
|------|-----------|
| `vendor\wheels` 없음 / .whl 없음 | Release zip을 `vendor\wheels\`에 풀었는지 (한 겹 폴더 주의) |
| Setup에서 패키지 설치 실패 | Python이 **3.12 x64**인지 (`py -3.12 --version`) |
| `RunWeb.bat` → `.venv` 없음 | `SetupOffline.bat`을 먼저 실행했는지 |
| streamlit / catboost import 오류 | Setup 재실행, VC++ Redistributable x64 설치 |
| 웹은 뜨는데 데이터 오류 | `configs\local.yaml`의 `data_root`, raw 파일 위치 |
| 포트 사용 중 | 기존 RunWeb 창을 닫거나, 콘솔에 표시된 다른 포트(8502 등) 사용 |

---

## 7. GitHub에 올리지 않는 것 (보안)

| 항목 | 위치 |
|------|------|
| raw CSV | `{data_root}\raw`, `raw_inference` 만 |
| 모델·행단위 점수 | `{data_root}\algorithms\...` |
| 운영 DB | `{data_root}\ops\ops.sqlite` |
| PC 경로 설정 | `configs\local.yaml` (gitignore) |

민감 데이터는 USB로 **오프라인 PC끼리만** 옮기고, GitHub·클라우드에 올리지 마세요.

---

## 부록. 관리자 — wheel 묶음을 새로 만들 때 (온라인 PC)

일반 사용자는 **이 절을 건너뛰면 됩니다.**  
이미 [v0.2.0 Release](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases/tag/v0.2.0)에 zip이 있습니다.

버전·패키지를 올릴 때만:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_wheels.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\upload_wheels_release.ps1
```

- 결과 zip: `dist\wheels-win-amd64-py312.zip`  
- 업로드: 위 스크립트 또는 Releases → Attach binaries
