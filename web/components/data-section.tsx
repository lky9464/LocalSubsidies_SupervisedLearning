"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPut, apiUpload } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { LoadingSpinner } from "@/components/loading-spinner";

type MetaItem = {
  id?: number | string;
  filename?: string;
  row_count?: number | string;
  registered_at?: string;
  note?: string;
  selected?: boolean;
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
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-lg rounded-lg border bg-background p-6 shadow-lg"
      >
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

export function DataSection({
  title,
  caption,
  kind,
  defaultCollapsed = false,
  onSelectionSaved,
  statusLabel = "",
  compactHeader = false,
}: {
  title: string;
  caption: string;
  kind: "train" | "inference";
  defaultCollapsed?: boolean;
  onSelectionSaved?: () => void;
  /** 제목 뒤 상태 표기 예: "(선택 저장됨)" */
  statusLabel?: string;
  /** 학습 실행 패널 등 — Train/Test 분할과 동일한 제목 크기 */
  compactHeader?: boolean;
}) {
  const path = kind === "train" ? "/api/data/raw" : "/api/data/raw-inference";
  const selectionPath = `${path}/selection`;
  const inputRef = useRef<HTMLInputElement>(null);
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const [deleteMode, setDeleteMode] = useState(false);
  const [deleteIds, setDeleteIds] = useState<Set<number>>(new Set());
  const [activeIds, setActiveIds] = useState<Set<number>>(new Set());
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
  const selectedCount = activeIds.size;
  const savedSelectedCount = items.filter((it) => it.selected).length;

  useEffect(() => {
    const next = new Set<number>();
    for (const it of items) {
      if (it.selected) next.add(Number(it.id));
    }
    setActiveIds(next);
  }, [data]);

  useEffect(() => {
    if (savedSelectedCount > 0 && !msg) setCollapsed(true);
  }, [savedSelectedCount, msg]);

  async function upload(files: File[], confirm = false) {
    setBusy(true);
    setMsg("");
    try {
      const res = await apiUpload<{ saved?: number; needs_confirm?: boolean; message?: string }>(
        path,
        files,
        confirm ? { confirm_add: "true" } : undefined,
      );
      if (res.needs_confirm) {
        setPendingFiles(files);
        setConfirmOpen(true);
      } else {
        setMsg(
          `${res.saved ?? files.length}개 파일 저장 완료 (기본 선택됨). 필요 시 체크를 조정한 뒤 「선택 저장」하세요.`,
        );
        setCollapsed(false);
        await refetch();
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "업로드 실패");
    } finally {
      setBusy(false);
    }
  }

  async function saveSelection() {
    setBusy(true);
    setMsg("");
    try {
      const res = await apiPut<{ selected_count: number }>(selectionPath, {
        ids: [...activeIds],
      });
      setMsg(
        res.selected_count > 0
          ? `선택 저장 완료: ${res.selected_count}개 파일이 다음 ${kind === "train" ? "학습" : "추론"}에 사용됩니다.`
          : "선택이 비어 있습니다. 학습/추론 전에 1개 이상 선택하세요.",
      );
      await refetch();
      onSelectionSaved?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "선택 저장 실패");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSelected() {
    if (!deleteIds.size) return;
    setBusy(true);
    try {
      await apiDelete(`${path}?ids=${[...deleteIds].join(",")}`);
      setDeleteIds(new Set());
      setDeleteMode(false);
      setMsg("선택한 파일을 삭제했습니다.");
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
      setMsg("전체 삭제 완료");
      setCollapsed(false);
      await refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "초기화 실패");
    } finally {
      setBusy(false);
    }
  }

  const allSelected = items.length > 0 && selectedCount === items.length;
  const summaryLabel =
    savedSelectedCount > 0
      ? `${savedSelectedCount}개 파일 선택 저장됨`
      : items.length
        ? "사용할 CSV를 체크한 뒤 선택 저장"
        : "등록된 CSV 없음";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className={compactHeader ? "text-sm font-semibold" : "text-base font-semibold"}>
            {title}
            {statusLabel ? ` ${statusLabel}` : ""}
          </h3>
          {!collapsed ? (
            <p
              className={
                compactHeader
                  ? "mt-1 text-xs text-muted-foreground"
                  : "mt-1 text-sm text-muted-foreground"
              }
            >
              {caption}
            </p>
          ) : null}
        </div>
        <Button variant="outline" size="sm" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? "펼치기" : "접기"}
        </Button>
      </div>

      {collapsed ? (
        <p className="text-sm text-muted-foreground">{summaryLabel}</p>
      ) : (
        <>
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

          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-medium">
              등록 풀 · 사용 선택{" "}
              <span className="font-normal text-muted-foreground">
                (체크된 {selectedCount}개 → 다음 {kind === "train" ? "학습" : "추론"})
              </span>
            </h4>
            <div className="flex flex-wrap gap-2">
              {!deleteMode ? (
                <>
                  <Button size="sm" onClick={() => void saveSelection()} disabled={busy || !items.length}>
                    선택 저장
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (allSelected) setActiveIds(new Set());
                      else setActiveIds(new Set(items.map((it) => Number(it.id))));
                    }}
                    disabled={!items.length}
                  >
                    {allSelected ? "전체 해제" : "전체 선택"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDeleteMode(true)}
                    disabled={!items.length}
                  >
                    삭제 모드
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
              ) : (
                <>
                  <Button variant="outline" size="sm" onClick={() => setDeleteMode(false)}>
                    취소
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => void deleteSelected()}
                    disabled={!deleteIds.size || busy}
                  >
                    선택 삭제
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
          ) : !items.length ? (
            <p className="text-sm text-muted-foreground">등록 메타 없음</p>
          ) : (
            <ul className="max-h-72 space-y-2 overflow-auto rounded-md border bg-muted/30 p-3 text-sm">
              {items.map((it) => {
                const id = Number(it.id);
                const checked = deleteMode ? deleteIds.has(id) : activeIds.has(id);
                return (
                  <li key={id}>
                    <label className="flex cursor-pointer flex-wrap items-center gap-2">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          if (deleteMode) {
                            const next = new Set(deleteIds);
                            if (e.target.checked) next.add(id);
                            else next.delete(id);
                            setDeleteIds(next);
                          } else {
                            const next = new Set(activeIds);
                            if (e.target.checked) next.add(id);
                            else next.delete(id);
                            setActiveIds(next);
                          }
                        }}
                      />
                      <span className="font-mono text-xs sm:text-sm">{String(it.filename ?? "")}</span>
                      <span className="text-muted-foreground">
                        {it.row_count != null ? `${Number(it.row_count).toLocaleString()}행` : "행수?"}
                      </span>
                      {!deleteMode && it.selected ? (
                        <span className="text-xs text-emerald-700">저장됨·사용</span>
                      ) : null}
                      <span className="text-xs text-muted-foreground">
                        {String(it.registered_at || "").slice(0, 19).replace("T", " ")}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}

      {confirmOpen ? (
        <SimpleModal title="풀에 추가 등록" onClose={() => setConfirmOpen(false)}>
          <p className="mb-4 text-sm">
            이미 등록된 데이터가 있습니다. 풀에 추가하시겠습니까? 학습/추론에 쓸 파일은 목록에서
            체크한 뒤 「선택 저장」하세요.
          </p>
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
              추가 등록
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
    </div>
  );
}
