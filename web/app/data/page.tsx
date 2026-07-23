"use client";

import { useEffect } from "react";
import { hardNavigate } from "@/lib/navigation";

/** @deprecated 데이터 등록은 학습 실행·추론 실행 화면으로 통합됨 */
export default function DataPage() {
  useEffect(() => {
    hardNavigate("/pipeline/");
  }, []);
  return (
    <p className="text-sm text-muted-foreground">학습 실행 화면으로 이동 중...</p>
  );
}
