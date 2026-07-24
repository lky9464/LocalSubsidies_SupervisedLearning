# 오프라인 업데이트 (변동분만 반영)

이미 **1회 설치**(`SetupOffline.bat` · `data_root` · raw)가 끝난 PC에서,  
프로젝트 폴더를 통째로 바꾸지 않고 **릴리스 변동분만** 덮어씁니다.

> **보존됨 (건드리지 않음)**  
> `configs\local.yaml` · `.venv` · `vendor\wheels` · `{data_root}`(프로젝트 밖 raw·모델·DB)

상세 설치는 [`offline_setup.md`](offline_setup.md) · 일상 사용은 [`user_guide.md`](user_guide.md)

---

## 1. 언제 무엇을 하면 되나

| 상황 | 할 일 | yaml / raw / whl |
|------|--------|------------------|
| **UI·버그 패치** (대부분) | `UpdateOffline.bat` + 서버 재시작 | **불필요** |
| **UI만** 바뀜 | `web-out.zip` → `web\out\` (또는 업데이트 zip) | 불필요 |
| **`requirements.txt` 변경** 릴리스 | 업데이트 후 **`SetupOffline.bat`** | **whl 재설치** |
| PC·경로 변경 | `configs\local.yaml`만 수정 | raw는 `{data_root}`에 그대로 |
| **최초 설치** | [`offline_setup.md`](offline_setup.md) 전체 절차 | 필요 |

릴리스마다 **어떤 유형인지**는 [`VERSION_HISTORY.md`](VERSION_HISTORY.md) 해당 버전의 **「오프라인 업데이트」** 줄과  
루트 [`offline_update_manifest.json`](../offline_update_manifest.json)을 참고합니다.

---

## 2. USB에 넣을 것 (온라인 PC에서 준비)

### 방법 A — 업데이트 zip (권장)

관리 PC(또는 Release Assets)에서:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_offline_update_package.ps1
```

→ `dist\update-v0.5.1.zip` 생성. USB에 복사.

Release에 `update-v*.zip`이 첨부되어 있으면 그 파일만 받아도 됩니다.

### 방법 B — Release 파일 수동 조합

같은 버전 Release에서:

| 파일·폴더 | 용도 |
|-----------|------|
| **`update-vX.Y.Z.zip`** 또는 아래 수동 | 변동분 묶음 |
| **`web-out.zip`** | UI (`web\out\`) |
| Source zip에서 **릴리스 노트에 적힌 폴더만** | 예: `api\`, `src\`, `scripts\`, `docs\` |

수동 조합 시 폴더 하나에 모아 `offline_update_manifest.json` + `web-out.zip` + 변경 폴더가 함께 있어야  
`UpdateOffline.bat`이 동작합니다. (방법 A가 실수가 적습니다.)

---

## 3. 오프라인 PC 적용 순서

1. **`RunWebNext.bat` 창을 닫아** 서버 중지  
2. 프로젝트 루트에서:

   ```text
   UpdateOffline.bat D:\USB\update-v0.5.1.zip
   ```

   또는 압축을 푼 폴더:

   ```text
   UpdateOffline.bat D:\USB\update-v0.5.1
   ```

3. 화면 안내 확인  
   - **「SetupOffline.bat」** 이라고 나오면 → whl 재설치 후 진행  
   - 그렇지 않으면 → **`RunWebNext.bat restart`**  
4. 브라우저 `http://127.0.0.1:8600` 새로고침 · 설정 → 버전 정보에서 버전 확인

`configs\local.yaml` · raw · `{data_root}`는 **다시 설정하지 않아도** 됩니다.

---

## 4. 수동 덮어쓰기 (스크립트 없이)

릴리스 노트·매니페스트에 적힌 경로만 Source zip / USB에서 복사합니다.

**절대 덮어쓰지 않음**

- `configs\local.yaml`
- `.venv\`
- `vendor\wheels\`

**v0.5.0 → v0.5.1 예시 (패치)**

| 복사 | 필요 |
|------|------|
| `api\`, `src\`, `scripts\`, `tests\`, `docs\` | ✅ |
| `web-out.zip` → `web\out\` | ✅ |
| `offline_update_manifest.json`, `UpdateOffline.bat`, `scripts\apply_offline_update.ps1` | ✅ (다음 업데이트용) |
| `configs\local.yaml`, raw, wheels, `SetupOffline.bat` | ❌ |

---

## 5. 문제 해결

| 증상 | 확인 |
|------|------|
| `offline_update_manifest.json not found` | zip 루트에 매니페스트 있는지 · 방법 A zip 사용 |
| Version mismatch | `-Force`는 관리자용. 보통 **직전 버전에서 한 단계씩** 업데이트 |
| UI만 옛날 | `web-out.zip` 반영 · `RunWebNext.bat restart` |
| import 오류 | `requirements.txt` 변경 릴리스 → `SetupOffline.bat` |
| data_root / raw | 업데이트와 무관 — `configs\local.yaml` · `{data_root}` 확인 |

---

## 6. 관리자 — 릴리스마다 할 일

1. [`offline_update_manifest.json`](../offline_update_manifest.json)에 새 `releases[]` 항목 추가  
   (`update_type`, `from_versions`, `extra_copy_paths`, `wheels_reinstall`)  
2. [`VERSION_HISTORY.md`](VERSION_HISTORY.md) 해당 버전에 **「오프라인 업데이트」** 한 줄 추가  
3. `build_offline_update_package.ps1` → `dist\update-vX.Y.Z.zip`  
4. GitHub Release Assets에 **`update-vX.Y.Z.zip`** · **`web-out.zip`** 첨부  
5. `requirements.txt`가 바뀌면 **`wheels-win-amd64-py312.zip`**도 재생성·첨부

`update_types` 요약:

| `update_type` | 의미 |
|---------------|------|
| `ui_only` | `web-out.zip`만 |
| `app_code` | `api`, `src`, `scripts` + UI (일반 패치) |
| `app_full` | 코드 + `docs` + 배치 + 설정 **예제** |
| `deps_changed` | `requirements.txt` + **SetupOffline** 필수 |
