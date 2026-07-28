# 오프라인 업데이트 (최신으로 full sync)

이미 **1회 설치**(`SetupOffline.bat` · `data_root` · raw)가 끝난 PC에서,  
프로젝트 폴더를 통째로 바꾸지 않고 **최신 릴리스로 동기화**합니다.

> **보존됨 (건드리지 않음)**  
> `configs\local.yaml` · `.venv` · `vendor\wheels`(갱신 전까지) · `vendor\python` · `{data_root}`(프로젝트 밖 raw·모델·DB)

상세 설치는 [`offline_setup.md`](offline_setup.md) · 일상 사용은 [`user_guide.md`](user_guide.md)

---

## 1. 권장 절차 (더블클릭)

1. **`RunWebNext.bat` 창을 닫아** 서버 중지  
2. GitHub Release에서 **`update-to-vX.Y.Z.zip`** 을 받아 **프로젝트 루트**에 복사  
   - **압축은 풀지 않음** (`.zip` 그대로 둠)  
   - **v0.5.2 기준(최초 full sync)**: 같은 폴더에 **`wheels-win-amd64-py312.zip`** 도 함께 둠  
   - 이후 릴리스는 `requirements.txt`가 바뀔 때만 wheels zip 필요  
3. **`UpdateOffline.bat` 실행**  
   - **신버전**(문구: `Offline update to latest`): 더블클릭만 하면 zip 자동 탐색  
   - **구버전**(문구: `Offline update (changed files only)` / Usage만 표시): zip 안의 새 배치를 먼저 꺼낸 뒤 재실행 — [§5-1](#5-1-updateofflinebat)  
4. 화면 **Next:** 안내 확인 → 보통 **`SetupOffline.bat`** — [§5-2](#5-2-setupofflinebat)  
5. **`RunWebNext.bat`** — UI가 비면 [§5-3](#5-3-runwebnextbat--webout)  
6. 브라우저 `http://127.0.0.1:8600` 새로고침 · 설정 → 버전 정보 확인

`configs\local.yaml` · raw · `{data_root}`는 **다시 설정하지 않아도** 됩니다.

선택: UI에 예전·섞인 결과가 보이면 **`CleanupLegacy.bat`** (raw 유지). 자동 실행하지 않습니다.

---

## 2. 언제 무엇을

| 상황 | 할 일 | yaml / raw / whl |
|------|--------|------------------|
| **v0.3.0 이상 → 최신** (권장) | `UpdateOffline.bat` + (필요 시) SetupOffline | yaml·raw 불필요 · **baseline/deps 변경 시 whl** |
| **UI만** 바뀜 (구형 hop) | `web-out.zip` → `web\out\` | 불필요 |
| PC·경로 변경 | `configs\local.yaml`만 수정 | raw는 `{data_root}`에 그대로 |
| **최초 설치** | [`offline_setup.md`](offline_setup.md) 전체 | 필요 |

릴리스 유형은 [`VERSION_HISTORY.md`](VERSION_HISTORY.md) **「오프라인 업데이트」** 줄과  
루트 [`offline_update_manifest.json`](../offline_update_manifest.json)을 참고합니다.

---

## 3. USB에 넣을 것 (온라인 PC)

### 방법 A — 업데이트 zip (권장)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_offline_update_package.ps1
```

→ `dist\update-to-v0.5.2.zip` 생성. USB에 복사.

Release에 `update-to-v*.zip`이 있으면 그 파일만 받아도 됩니다.  
**wheels_baseline / requirements 변경** 릴리스면 **`wheels-win-amd64-py312.zip`**도 같이 넣습니다.

### 방법 B — 경로 지정

```text
UpdateOffline.bat D:\USB\update-to-v0.5.2.zip
UpdateOffline.bat D:\USB\update-to-v0.5.2.zip /autowheels
```

`/autowheels`: wheels zip이 있으면 풀고 `SetupOffline.bat`까지 이어서 실행.

구형 이름 `update-vX.Y.Z.zip`도 자동 탐색에 포함됩니다.

---

## 4. 보존·덮어쓰기

**절대 덮어쓰지 않음**

- `configs\local.yaml`
- `.venv\`
- `vendor\python\`
- `{data_root}` 전체

**갱신될 수 있음**

- `api\`, `src\`, `scripts\`, `tests\`, `docs\`, `web\out\`
- `requirements.txt` · 배치 파일 · 매니페스트
- `configs\default.yaml` · `local.yaml.example`만 (local.yaml 제외)
- baseline/deps 시 `vendor\wheels\` (wheels zip에서 재배치)

---

## 5. 문제 해결

| 증상 | 확인 |
|------|------|
| No update zip found | 프로젝트 루트에 `update-to-vX.Y.Z.zip` 두었는지 |
| Version too old (from_min) | v0.3.0 미만 → Source zip으로 재설치 |
| UI만 옛날 / `web\out` 비어 있음 | [§5-3](#5-3-runwebnextbat--webout) |
| import 오류 | wheels zip + `SetupOffline.bat` |
| data_root / raw | 업데이트와 무관 — `configs\local.yaml` 확인 |
| 예전 결과 섞임 | 선택적으로 `CleanupLegacy.bat` (raw 유지) |

### 5-1. UpdateOffline.bat

**증상:** 더블클릭 후 `Offline update (changed files only)` · `Usage: UpdateOffline.bat [update_folder_or_zip]` 만 나오고 종료 (업데이트 미실행).

**원인:** PC에 남아 있는 **구버전** 배치. 인자 없이는 Usage만 표시하며, 새 배치는 `update-to-*.zip` 안에만 있음.

**대처:**

1. `update-to-v0.5.2.zip`을 임시 폴더(예: `_upd`)에만 압축 해제  
2. 풀린 내용에서 아래를 **프로젝트 루트에 덮어쓰기**  
   - `UpdateOffline.bat`  
   - `scripts\apply_offline_update.ps1`  
3. 임시 폴더 삭제 가능  
4. 루트에 zip 2개가 있는 상태에서 **`UpdateOffline.bat` 더블클릭**  
   - 또는: `UpdateOffline.bat update-to-v0.5.2.zip`

성공 시 문구는 `Offline update to latest` · `[update] copy: ...` 등이 이어집니다.

### 5-2. SetupOffline.bat

**증상:** `[3/4] Installing packages...` 에서  
`Fatal error in launcher: Unable to create process using '"...-0.5.0\.venv\Scripts\python.exe" "...-0.5.1\.venv\Scripts\pip.exe" ...'`

**원인:** 프로젝트 폴더를 이름 변경·복사한 뒤 **옛 경로가 박힌 `.venv`** 를 그대로 씀. UpdateOffline는 `.venv`를 보존함.

**대처:**

1. `RunWebNext` 종료  
2. 프로젝트 루트의 **`.venv` 폴더만 삭제** (`local.yaml` · `vendor\wheels` · data_root · raw는 유지)  
3. **`SetupOffline.bat` 다시 실행**  
4. **`RunWebNext.bat`**

`vendor\wheels`에 `.whl`이 없으면 `wheels-win-amd64-py312.zip`을 `vendor\wheels\`에 풀어 둔 뒤 SetupOffline를 재실행합니다.

### 5-3. RunWebNext.bat · web/out

**증상:** 서버는 뜨는데 UI가 비거나 깨짐 · `web\out\index.html` 없음.

**원인:** Update 중 UI(`web-out.zip` → `web\out\`) 반영이 누락된 경우.

**대처 (택1):**

1. **권장:** Release의 **`web-out.zip`** (또는 `update-to-v0.5.2.zip` 안의 `web-out.zip`)을 풀어 **`web\out\`** 이 되게 함 (`web\out\index.html` 확인)  
2. **대안:** `update-to-v0.5.2.zip`을 임시 해제했을 때 안에 `web\out\` 또는 `web-out.zip`이 있으면 그 내용을 프로젝트 `web\out\`에 붙여넣기  
3. **`RunWebNext.bat` 재실행** · 브라우저 강력 새로고침

---

## 6. 관리자 — 릴리스마다 할 일

1. [`offline_update_manifest.json`](../offline_update_manifest.json)  
   - `target_version` / `releases[]` (보통 `full_sync`, `from_min: 0.3.0`)  
   - deps 바뀌면 `wheels_reinstall: true` · 최초 baseline은 `wheels_baseline: true`  
2. [`VERSION_HISTORY.md`](VERSION_HISTORY.md)에 **「오프라인 업데이트」** 한 줄  
3. `build_offline_update_package.ps1` → `dist\update-to-vX.Y.Z.zip`  
4. GitHub Release Assets: **`update-to-vX.Y.Z.zip`** · **`web-out.zip`**  
5. baseline/deps 시 **`wheels-win-amd64-py312.zip`**도 첨부

`update_types` 요약:

| `update_type` | 의미 |
|---------------|------|
| `full_sync` | v0.3.0+ → 최신 전체 동기화 (**권장**) |
| `ui_only` | `web-out.zip`만 (레거시) |
| `app_code` | `api`/`src`/`scripts` + UI (레거시 hop) |
