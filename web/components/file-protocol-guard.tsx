"use client";

import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/alert";

export function FileProtocolGuard() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    setShow(window.location.protocol === "file:");
  }, []);

  if (!show) return null;

  return (
    <Alert variant="destructive" className="mx-6 mt-4 border-red-300">
      <p className="font-medium">잘못된 실행 방식 (file://)</p>
      <p className="mt-1 text-sm">
        <code className="rounded bg-red-100 px-1">web/out/index.html</code>을 더블클릭하면 메뉴 링크가{" "}
        <code className="rounded bg-red-100 px-1">C:/run-issue/</code> 등으로 깨집니다. API도 동작하지 않습니다.
      </p>
      <p className="mt-2 text-sm">
        프로젝트 루트에서 <strong>RunWebNext.bat</strong> 실행 →{" "}
        <strong>http://127.0.0.1:8600</strong> 으로 접속하세요.
      </p>
    </Alert>
  );
}
