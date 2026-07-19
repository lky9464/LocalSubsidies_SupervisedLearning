"use client";

import { useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiDelete, apiGet, apiUpload } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { LoadingSpinner } from "@/components/loading-spinner";

type MetaItem = {
  id?: number | string;
  filename?: string;
  row_count?: number | string;
  registered_at?: string;
  note?: string;
};

function SimpleModal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div role="dialog" aria-modal="true" className="w-full max-w-lg rounded-lg border bg-background p-6 shadow-lg">
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button type="button" className="text-sm text-muted-foreground" onClick={onClose}>
            닫기
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function MetaSummary({ items }: { items: MetaItem[] }) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">등록 메타 없음</p>;
  }
  const totalRows = items.reduce((sum, it) => {
    const n = Number(it.row_count);
    return sum + (Number.isFinite(n) ? n : 0);
  }, 0);
  return (
    <div className="space-y-2">
      <p className="text-sm">
        <span className="font-medium">{items.length}개 파일</span>
        <span className="text-muted-foreground"> · 합계 약 {totalRows.toLocaleString()}행</span>
      </p>
      <ul className="max-h-56 space-y-1 overflow-auto rounded-md border bg-muted/30 p-3 text-sm">
        {items.map((it) => (
          <li key={String(it.id)} className="flex flex-wrap gap-x-3 gap-y-0.5">
            <span className="font-mono text-xs sm:text-sm">{String(it.filename ?? "")}</span>
            <span className="text-muted-foreground">
              {it.row_count != null ? `${Number(it.row_count).toLocaleString()}행` : "행수?"}
            </span>
            <span className="text-xs text-muted-foreground">
              {String(it.registered_at || "").slice(0, 19).replace("T", " ")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DataSection({
  title,
  caption,
  kind,
}: {
  title: string;
  caption: string;
  kind: "train" | "inference";
}) {
  const path = kind === "train" ? "/api/data/raw" : "/api/data/raw-inference";
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [clearOpen, setClearOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["data", kind],
    queryFn: ({ signal }) =>
      apiGet<{ items: MetaItem[] }>(path, { signal, timeoutMs: 10_000 }),
    retry: 1,
    staleTime: 30_000,
  });

  const items = Array.isArray(data?.items) ? data.items : [];

  async function upload(files: File[], confirm = false) {
    setBusy(true);
    setMsg("");
    try {
      const res = await apiUpload<{ saved?: number; needs_confirm?: boolean }>(
        path,
        files,
        confirm ? { confirm_add: "true" } : undefined,
      );
      if (res.needs_confirm) {
        setPendingFiles(files);
        setConfirmOpen(true);
      } else {
        setMsg(`${res.saved ?? files.length}개 파일 저장 및 메타 기록 완료`);
        await refetch();
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "업로드 실패");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSelected() {
    if (!selected.size) return;
    setBusy(true);
    try {
      await apiDelete(`${path}?ids=${[...selected].join(",")}`);
      setSelected(new Set());
      setSelectMode(false);
      await refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setBusy(false);
    }
  }

  async function clearAll() {
    setBusy(true);
    try {
      await apiDelete(`${path}/all`);
      setClearOpen(false);
      await refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "초기화 실패");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4 rounded-lg border p-6">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{caption}</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          multiple
          className="text-sm"
          onChange={(e) => {
            const files = [...(e.target.files || [])];
            if (files.length) void upload(files);
            e.target.value = "";
          }}
        />
        {(busy || isFetching) && <LoadingSpinner />}
      </div>
      {msg ? <Alert variant="success">{msg}</Alert> : null}

      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">등록 현황 (메타)</h3>
        <div className="flex gap-2">
          {selectMode ? (
            <>
              <Button variant="outline" size="sm" onClick={() => setSelectMode(false)}>
                취소
              </Button>
              <Button size="sm" onClick={() => void deleteSelected()} disabled={!selected.size || busy}>
                선택 삭제
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectMode(true)}
                disabled={!items.length}
              >
                선택 삭제
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setClearOpen(true)}
                disabled={!items.length}
              >
                초기화
              </Button>
            </>
          )}
        </div>
      </div>

      {isError ? (
        <Alert variant="destructive">
          메타 조회 실패: {error instanceof Error ? error.message : "알 수 없는 오류"}
          <Button variant="outline" size="sm" className="ml-3" onClick={() => void refetch()}>
            다시 시도
          </Button>
        </Alert>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">불러오는 중...</p>
      ) : selectMode ? (
        <div className="max-h-56 space-y-2 overflow-auto rounded-md border p-3">
          {items.map((item) => {
            const id = Number(item.id);
            return (
              <label key={id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selected.has(id)}
                  onChange={(e) => {
                    const next = new Set(selected);
                    if (e.target.checked) next.add(id);
                    else next.delete(id);
                    setSelected(next);
                  }}
                />
                {String(item.filename)} ({String(item.row_count ?? "?")}행)
              </label>
            );
          })}
        </div>
      ) : (
        <MetaSummary items={items} />
      )}

      {confirmOpen ? (
        <SimpleModal title="추가 등록 확인" onClose={() => setConfirmOpen(false)}>
          <p className="mb-4 text-sm">이미 등록된 데이터가 있습니다. 추가 등록하시겠습니까?</p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              취소
            </Button>
            <Button
              onClick={async () => {
                setConfirmOpen(false);
                await upload(pendingFiles, true);
                setPendingFiles([]);
              }}
            >
              등록
            </Button>
          </div>
        </SimpleModal>
      ) : null}

      {clearOpen ? (
        <SimpleModal title="전체 삭제 확인" onClose={() => setClearOpen(false)}>
          <p className="mb-4 text-sm text-red-600">
            메타와 로컬 파일이 모두 삭제됩니다. 계속하시겠습니까?
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setClearOpen(false)}>
              취소
            </Button>
            <Button variant="destructive" onClick={() => void clearAll()}>
              삭제
            </Button>
          </div>
        </SimpleModal>
      ) : null}
    </section>
  );
}

export default function DataPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">데이터 등록</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          업로드는 data_root 하위에만 저장됩니다. DB에는 파일명·행수 등 메타만 기록합니다.
        </p>
      </div>
      <DataSection
        title="학습·평가 raw 데이터"
        caption="TLS4902R 레이아웃 CSV(통상 8종). data_root/raw 에 저장됩니다."
        kind="train"
      />
      <DataSection
        title="추론 raw 데이터"
        caption="동일 레이아웃. TAET_YN 및 타겟 수정 3컬럼은 추론에서 무시됩니다. data_root/raw_inference."
        kind="inference"
      />
    </div>
  );
}
