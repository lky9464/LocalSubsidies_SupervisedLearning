# vendor/

오프라인 설치용 바이너리를 두는 자리입니다. **Git에는 wheel 실파일을 올리지 않습니다.**

## wheels/

1. [GitHub Releases](https://github.com/lky9464/LocalSubsidies_SupervisedLearning/releases)에서  
   `wheels-win-amd64-py312.zip` 다운로드  
2. 압축을 풀어 이 폴더에 `.whl` 파일이 오게 합니다:

```text
vendor/wheels/*.whl
```

3. 프로젝트 루트에서 `SetupOffline.bat` 실행

관리자가 새로 만들 때(온라인 PC):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_offline_wheels.ps1
```

상세: [`docs/offline_setup.md`](../docs/offline_setup.md)
