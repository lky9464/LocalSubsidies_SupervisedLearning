"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";

async function fetchMd(path: string) {
  const res = await fetch(path);
  if (!res.ok) throw new Error("문서 없음");
  return res.text();
}

export default function GuidePage() {
  const [msg, setMsg] = useState("");

  const intro = useQuery({
    queryKey: ["guideIntro"],
    queryFn: () => fetchMd("/api/guide/intro"),
  });

  const user = useQuery({
    queryKey: ["guideUser"],
    queryFn: () => fetchMd("/api/guide/user"),
  });

  async function genIntro() {
    await apiPost("/api/guide/generate/intro");
    setMsg("소개 PDF 생성 완료");
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">사용자 가이드</h1>
      </div>

      {msg && <Alert variant="success">{msg}</Alert>}

      <section className="space-y-3">
        <h2 className="text-lg font-medium">프로젝트 소개 (권장)</h2>
        <details className="rounded-lg border p-4">
          <summary className="cursor-pointer font-medium">소개 문서 미리보기</summary>
          <div className="prose prose-sm mt-4 max-w-none dark:prose-invert whitespace-pre-wrap text-sm">
            {intro.isLoading ? "로딩..." : intro.error ? "문서 없음" : intro.data}
          </div>
        </details>
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <a href="/api/guide/intro.pdf" download>
              소개 PDF 다운로드
            </a>
          </Button>
          <Button variant="outline" onClick={genIntro}>
            소개 PDF 생성
          </Button>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">웹 조작 요약</h2>
        <details className="rounded-lg border p-4">
          <summary className="cursor-pointer font-medium">user_guide.md</summary>
          <div className="prose prose-sm mt-4 max-w-none dark:prose-invert whitespace-pre-wrap">
            {user.isLoading ? "로딩..." : user.error ? "문서 없음" : user.data}
          </div>
        </details>
        <Button variant="secondary" asChild>
          <a href="/api/guide/user.pdf" download>
            요약 PDF 다운로드
          </a>
        </Button>
      </section>
    </div>
  );
}
