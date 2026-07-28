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
   - **v0.5.2 기준(최초 full sync)**: 같은 폴더에 **`wheels-win-amd64-py312.zip`** 도 함께 둠  
   - 이후 릴리스는 `requirements.txt`가 바뀔 때만 wheels zip 필요  
3. **`UpdateOffline.bat` 더블클릭** (인자 없이 OK — zip 자동 탐색)  
4. 화면 **Next:** 안내 확인  
   - wheels가 풀렸으면 → **`SetupOffline.bat`** 후 **`RunWebNext.bat restart`**  
   - 아니면 → **`RunWebNext.bat restart`** 만  
5. 브라우저 `http://127.0.0.1:8600` 새로고침 · 설정 → 버전 정보 확인

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
| UI만 옛날 | `web-out.zip` 반영 · `RunWebNext.bat restart` · 브라우저 강력 새로고침 |
| import 오류 | wheels zip + `SetupOffline.bat` |
| data_root / raw | 업데이트와 무관 — `configs\local.yaml` 확인 |
| 예전 결과 섞임 | 선택적으로 `CleanupLegacy.bat` (raw 유지) |

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
