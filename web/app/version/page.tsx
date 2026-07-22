"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

type VersionEntry = {
  version?: string;
  title?: string;
  bullets?: string[];
  release_url?: string | null;
};

type VersionPayload = {
  current_version?: string;
  entries?: VersionEntry[];
  source?: string;
};

export default function VersionPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["versionInfo"],
    queryFn: () => apiGet<VersionPayload>("/api/version"),
    staleTime: 60_000,
  });

  const current = data?.current_version || "";
  const entries = Array.isArray(data?.entries) ? data.entries : [];

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">버전 정보</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          공식 릴리스 버전과 변경 이력입니다. 원문: docs/VERSION_HISTORY.md
        </p>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">불러오는 중...</p>
      ) : isError ? (
        <Alert variant="destructive">
          {error instanceof Error ? error.message : "버전 정보를 불러오지 못했습니다."}
        </Alert>
      ) : (
        <>
          <section className="rounded-lg border bg-muted/20 p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              현재 버전
            </p>
            <p className="mt-2 text-3xl font-semibold tracking-tight">{current || "(미정)"}</p>
            <p className="mt-2 text-sm text-muted-foreground">
              GitHub Release 기준 공식 버전입니다.
            </p>
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-medium">버전 노트</h2>
            {!entries.length ? (
              <p className="text-sm text-muted-foreground">등록된 항목이 없습니다.</p>
            ) : (
              <ul className="space-y-4">
                {entries.map((e) => {
                  const ver = String(e.version || "");
                  const isCurrent =
                    current &&
                    (ver === current || ver.startsWith(current) || current.startsWith(ver.split(/\s/)[0]));
                  return (
                    <li key={ver} className="rounded-lg border p-4">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <h3 className="font-semibold">
                            {ver}
                            {e.title ? (
                              <span className="font-normal text-muted-foreground">
                                {" "}
                                — {e.title}
                              </span>
                            ) : null}
                          </h3>
                        </div>
                        {isCurrent ? <Badge>현재</Badge> : null}
                      </div>
                      {e.bullets?.length ? (
                        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                          {e.bullets.map((b) => (
                            <li key={b}>{b}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-3 text-sm text-muted-foreground">상세 항목 없음</p>
                      )}
                      {e.release_url ? (
                        <p className="mt-3 text-xs">
                          <a
                            href={e.release_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary underline"
                          >
                            Release / Tag 보기
                          </a>
                        </p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
