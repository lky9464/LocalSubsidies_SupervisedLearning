# Next.js Web UI (정적 export)

로컬 ML 운영 콘솔 프론트엔드. FastAPI(`api/`)가 `web/out/` 정적 파일을 서빙합니다.

## 개발 (Node.js 필요 — 온라인 PC)

```powershell
cd web
npm install
npm run dev          # http://127.0.0.1:3000 (API는 별도 uvicorn 필요)
npm run build        # web/out/ 생성
```

또는 프로젝트 루트에서 **`scripts/build_web.bat`**

## 오프라인 PC

- **Node 런타임 불필요** — 사전 빌드된 `web/out/`만 있으면 됩니다.
- Release zip에 `web/out/` 포함 (관리자가 온라인 PC에서 `build_web.bat` 실행 후 동봉).

## API 연동

- 정적 export이므로 API 호출은 동일 오리진 `/api/*` (FastAPI `127.0.0.1:8600`).
- React Query로 Job 2초 폴링, Run 컨텍스트는 `/api/session/current-run`.

## 기술 스택

- Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui 스타일 컴포넌트
- Recharts (모델 방사형 차트), lucide-react, next-themes (라이트 기본)
