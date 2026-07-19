# 오프라인 사용법

인터넷이 없는 PC에서 이 프로젝트를 설치·실행하는 순서입니다.  
GitHub에서 **소스 + Release 자산**을 받아 USB 등으로 옮긴 뒤, 아래 순서대로 진행하면 됩니다.

> **한 줄 요약**  
> 소스 ZIP + Release의 `wheels-win-amd64-py312.zip` (+ `web/out`) → Python 3.12 설치 → `SetupOffline.bat` → `data_root`·raw 준비 → `RunWebNext.bat`

---

## 0. 지원 환경 · 미리 알아둘 것

| 항목 | 내용 |
|------|------|
| OS | Windows 10 / 11 **64-bit** |
| Python | **3.12** x64 (wheel 묶음 기준) |
| 네트워크 | **설치·실행 시 인터넷 불필요** (wheel·UI를 미리 받아 둔 경우) |
| 데이터 | raw CSV는 GitHub에 **없음** — 사용자가 `{data_root}`에 직접 둠 |
| UI | FastAPI + Next 정적 export (`web/out`) · `http://127.0.0.1:8600` |

이 저장소에는 **코드·문서·스키마**만 있습니다.  
학습·추론용 CSV, 모델, 행단위 점수는 Release에도 포함되지 않습니다.

`web/out`(빌드된 UI)과 `vendor/wheels`는 git에 올리지 않습니다. **Release 업데이트**로 배포합니다.

---

## 1. (온라인 PC) GitHub에서 받을 것

온라인 가능한 PC에서 아래를 받아 USB·외장하드 등에 복사합니다.

### ① 소스 코드 (ZIP 또는 git pull)

1. 저장소: https://github.com/lky9464/LocalSubsidies_SupervisedLearning  
2. 초록색 **Code** → **Download ZIP** (또는 인가된 clone/pull)

### ② wheel 묶음 (패키지 설치용)

1. **Releases**: https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases  
2. 최신(또는 안내된) 태그 → Assets **`wheels-win-amd64-py312.zip`**

### ③ UI 정적 파일 (`web/out`)

오프라인 PC에 Node.js가 없으면 아래 중 하나가 필요합니다.

- Release Assets의 **`web-out.zip`** (권장)을 풀어 프로젝트의 `web\out\` 이 되게 함  
- 또는 온라인 PC에서 `scripts\build_web.bat` 실행 후 `web\out\` 폴더 전체를 USB로 복사

### (권장) Python 설치 파일도 함께

- Python 3.12 Windows **64-bit** installer  
  https://www.python.org/downloads/windows/  
- (선택) [VC++ Redistributable x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)

### USB에 넣을 목록 (체크)

- [ ] 소스 ZIP (또는 pull한 폴더)
- [ ] `wheels-win-amd64-py312.zip`
- [ ] `web-out.zip` 또는 빌드된 `web\out\`
- [ ] Python 3.12 x64 설치 파일 (필요 시)
- [ ] 학습·평가용 raw CSV (사용자 확보)

---

## 2. (오프라인 PC) 폴더 준비

### 2-1. 소스 압축 해제

```text
C:\work\LocalSubsidies_SupervisedLearning\
```

풀린 폴더에 `SetupOffline.bat`, `RunWebNext.bat`, `api\`, `web\` 등이 보이면 됩니다.

### 2-2. wheel을 올바른 위치에 풀기

```text
LocalSubsidies_SupervisedLearning\
├── SetupOffline.bat
├── RunWebNext.bat
├── InitDataRoot.bat
├── requirements.lock.txt
├── web\
│   └── out\                 ← UI (index.html 등)
└── vendor\
    └── wheels\
        ├── numpy-....whl
        ├── fastapi-....whl
        ├── catboost-....whl
        └── ... (수십 개)
```

**주의:** zip 안에 `wheels` 폴더가 한 겹 더 있으면  
`vendor\wheels\wheels\*.whl` 이 되지 않도록 **`.whl`이 바로 `vendor\wheels\` 아래** 있게 옮기세요.

### 2-3. Python 3.12 설치

```text
py -3.12 --version
```

---

## 3. (오프라인 PC) 프로그램 설치 — 1회

프로젝트 루트에서 **`SetupOffline.bat`** 을 더블클릭합니다.

1. `.venv` 가상환경 생성  
2. `vendor\wheels`의 패키지를 인터넷 없이 설치  
3. `configs\local.yaml`이 없으면 예제에서 복사  

---

## 4. 데이터 경로 · raw 배치

```text
notepad configs\local.yaml
```

```yaml
data_root: "C:/work/LocalSubsidies_ML_Data"
```

이어서 **`InitDataRoot.bat`** → raw를 `{data_root}\raw\`, 추론은 `raw_inference\`에 배치.  
스키마: [`TLS4902R_Layout.csv`](../TLS4902R_Layout.csv)

---

## 5. 실행 (일상)

1. `web\out\index.html` 이 있는지 확인 (없으면 §1 ③)  
2. **`RunWebNext.bat`** 더블클릭 → `http://127.0.0.1:8600`  
3. **검은 콘솔 창을 닫지 마세요**

상세: [`user_guide.md`](user_guide.md) · [`web_local.md`](web_local.md)

이후 재실행은 **`RunWebNext.bat`만** 다시 누르면 됩니다.

---

## 6. 문제 해결

| 증상 | 확인할 것 |
|------|-----------|
| `vendor\wheels` 없음 / .whl 없음 | Release zip을 `vendor\wheels\`에 풀었는지 |
| Setup에서 패키지 설치 실패 | Python이 **3.12 x64**인지 |
| `RunWebNext.bat` → `.venv` 없음 | `SetupOffline.bat`을 먼저 실행했는지 |
| fastapi / catboost import 오류 | Setup 재실행, VC++ Redistributable x64 |
| UI가 안 뜨거나 빈 페이지 | `web\out\` 존재 여부 (Release `web-out.zip` 또는 `build_web.bat`) |
| `file://` 로 HTML만 연 경우 | 반드시 `RunWebNext.bat` → `http://127.0.0.1:8600` |
| 포트 사용 중 | 기존 RunWebNext 창을 닫은 뒤 재실행 |

---

## 7. GitHub에 올리지 않는 것 (보안)

| 항목 | 위치 |
|------|------|
| raw CSV | `{data_root}\raw`, `raw_inference` 만 |
| 모델·행단위 점수 | `{data_root}\algorithms\...` |
| 운영 DB | `{data_root}\ops\ops.sqlite` |
| PC 경로 설정 | `configs\local.yaml` (gitignore) |
| wheels / web/out | Release로만 배포 |

---

## 부록. 관리자 — Release 자산 갱신 (온라인 PC)

일반 사용자는 이 절을 건너뛰면 됩니다.

```powershell
# Python wheels
powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_wheels.ps1
# UI
cmd /c "echo.| scripts\build_web.bat"
# web\out 을 zip으로 묶어 Releases에 첨부 (wheels와 함께)
```

- wheels: `dist\wheels-win-amd64-py312.zip`  
- UI: `web\out\` → 예: `web-out.zip`  
- Streamlit 제거 후 wheels를 다시 만들면 용량이 줄어듭니다.
