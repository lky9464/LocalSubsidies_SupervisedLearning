# 오프라인 PC 설치 안내

GitHub ZIP(소스)만으로는 PyPI에 접속해 패키지를 받을 수 없습니다.  
**소스 + Release의 wheel 묶음**을 함께 쓰면 인터넷 없이 설치·실행할 수 있습니다.

## 지원 환경

| 항목 | 값 |
|------|-----|
| OS | Windows 10/11 **64-bit** |
| Python | **3.12** x64 (권장·wheel 기준) |
| 네트워크 | 설치 시 **불필요** (wheel이 `vendor/wheels`에 있을 때) |

## 준비물 (2개)

1. **소스** — Code → Download ZIP, 또는 clone  
2. **wheel 묶음** — [Releases](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases)의  
   `wheels-win-amd64-py312.zip`  
   (태그 예: `v0.2.0`)

raw CSV·모델·점수는 Release에 **없습니다**. `{data_root}`에 사용자가 직접 둡니다.

## 오프라인 PC 순서

### 1) 소스 압축 해제

원하는 폴더에 풀어 둡니다.  
예: `C:\work\LocalSubsidies_SupervisedLearning\`

### 2) wheel 풀기

`wheels-win-amd64-py312.zip`을 풀어 **아래 구조**가 되게 합니다.

```text
LocalSubsidies_SupervisedLearning\
├── SetupOffline.bat
├── RunWeb.bat
├── requirements.lock.txt
└── vendor\
    └── wheels\
        ├── numpy-....whl
        ├── streamlit-....whl
        └── ... (다수 .whl)
```

### 3) Python 3.12 설치

대상 PC에 Python 3.12 x64가 없으면, 미리 USB로 가져온  
공식 Windows 설치 파일로 설치합니다.  
(“Add python.exe to PATH” 권장)

numpy/catboost 오류 시 [VC++ Redistributable x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)를 설치합니다.

### 4) SetupOffline.bat

프로젝트 루트에서 **더블클릭**.

- `.venv` 생성  
- `vendor\wheels`에서 `requirements.lock.txt` 설치 (인터넷 없음)  
- `configs\local.yaml`이 없으면 예제 복사  

### 5) data_root 설정

```text
notepad configs\local.yaml
```

`data_root`를 본인 PC 경로로 수정  
(프로젝트와 **형제 폴더** `LocalSubsidies_ML_Data` 권장).

### 6) 폴더 골격 + raw 배치

```text
InitDataRoot.bat
```

그다음:

- 학습·평가 CSV → `{data_root}\raw\`  
- 추론 CSV → `{data_root}\raw_inference\`  
- 스키마: repo의 `TLS4902R_Layout.csv`

### 7) 실행

```text
RunWeb.bat
```

브라우저: `http://127.0.0.1:8501`  
(콘솔 창을 닫으면 서버가 종료됩니다.)

---

## 온라인 PC에서 wheel 묶음 만들기 (관리자용)

이미 Release에 zip이 있으면 **이 절은 생략**합니다.  
버전을 올릴 때만 개발 PC(인터넷 가능)에서:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_wheels.ps1
```

결과:

- `vendor\wheels\` — .whl 파일들  
- `dist\wheels-win-amd64-py312.zip` — Release 업로드용  

업로드 예:

```powershell
# 최초 1회: gh auth login
powershell -ExecutionPolicy Bypass -File .\scripts\upload_wheels_release.ps1
```

또는 GitHub 웹 → Releases → `v0.2.0` → Edit → **Attach binaries**에  
`dist\wheels-win-amd64-py312.zip` 드래그.

## 동봉하지 않는 것

| 항목 | 이유 |
|------|------|
| raw / 점수 / 모델 / `ops.sqlite` | 민감·대용량, 로컬 `{data_root}`만 |
| `.venv` | 머신·경로 의존 |
| `configs/local.yaml` | PC별 절대경로 |

## 문제 해결

| 증상 | 확인 |
|------|------|
| `vendor\wheels` 없음 | Release zip을 `vendor\wheels`에 풀었는지 |
| 패키지 설치 실패 | Python이 **3.12 x64**인지 |
| `RunWeb.bat`이 .venv 없음 | `SetupOffline.bat` 먼저 |
| streamlit import 오류 | Setup 로그 재확인, VC++ Redistributable |
| 웹은 뜨는데 데이터 오류 | `local.yaml`의 `data_root`, raw 파일 배치 |
