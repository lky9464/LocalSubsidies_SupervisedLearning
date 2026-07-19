import type { CSSProperties } from "react";
import type { MatrixPayload } from "@/lib/types";
import { cn, formatDisplayValue } from "@/lib/utils";

/** ops_queue.priority_from_bands 와 동일: 주×보 → 1(최우선)~16 */
const BAND_RANK: Record<string, number> = {
  주A: 0,
  주B: 1,
  주C: 2,
  주D: 3,
  보A: 0,
  보B: 1,
  보C: 2,
  보D: 3,
};

export function priorityFromBands(primary: string, aux: string): number {
  const p = BAND_RANK[primary] ?? 3;
  const a = BAND_RANK[aux] ?? 3;
  return p * 4 + a + 1;
}

/** 우선순위 1=진한 적색 … 16=옅은 적색 */
export function priorityHeatStyle(priority: number): CSSProperties {
  const p = Math.min(16, Math.max(1, priority));
  const t = (17 - p) / 16; // 1 → 1.0, 16 → ~0.06
  const lightness = 94 - t * 52; // ~42% … ~91%
  const saturation = 62 + t * 28;
  const textLight = t >= 0.5;
  return {
    backgroundColor: `hsl(0 ${saturation}% ${lightness}%)`,
    color: textLight ? "#fff7f7" : "#7f1d1d",
    fontWeight: t >= 0.65 ? 700 : t >= 0.4 ? 600 : 500,
  };
}

function PriorityLegend() {
  const samples = [1, 4, 8, 12, 16];
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
      <span className="font-medium text-slate-700">점검 우선순위</span>
      <span>높음</span>
      {samples.map((p) => (
        <span
          key={p}
          className="inline-flex h-5 min-w-[1.75rem] items-center justify-center rounded px-1 tabular-nums"
          style={priorityHeatStyle(p)}
          title={`우선순위 ${p}`}
        >
          {p}
        </span>
      ))}
      <span>낮음</span>
    </div>
  );
}

export function MatrixTable({
  matrix,
  title,
  caption,
  heatByPriority = false,
}: {
  matrix?: MatrixPayload | null;
  title?: string;
  caption?: string;
  /** 추론 점검용: 셀을 우선순위(1~16) 적색 스케일로 칠함 */
  heatByPriority?: boolean;
}) {
  if (!matrix?.data?.length) return null;
  return (
    <div className="space-y-2">
      {title && <h4 className="text-sm font-medium">{title}</h4>}
      {caption && <p className="text-xs text-muted-foreground">{caption}</p>}
      {heatByPriority ? <PriorityLegend /> : null}
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full min-w-[300px] border-collapse text-sm">
          <thead>
            <tr className="border-b">
              <th className="bg-slate-200/90 px-2 py-2.5 text-left">
                <span className="text-base font-bold tracking-tight text-slate-900">주</span>
                <span className="mx-0.5 font-normal text-slate-400">＼</span>
                <span className="text-xs font-medium text-slate-500">보</span>
              </th>
              {matrix.columns.map((c) => (
                <th
                  key={c}
                  className="bg-muted/40 px-2 py-2 text-center text-xs font-medium text-muted-foreground"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.index.map((row, ri) => (
              <tr key={row} className="border-b last:border-0">
                <th
                  scope="row"
                  className={cn(
                    "border-r-2 border-slate-400 bg-slate-100 px-2 py-2.5 text-left",
                    "text-[0.95rem] font-bold text-slate-900",
                  )}
                >
                  {row}
                </th>
                {matrix.data[ri]?.map((val, ci) => {
                  const col = matrix.columns[ci] ?? "";
                  const pri = heatByPriority ? priorityFromBands(row, col) : null;
                  return (
                    <td
                      key={ci}
                      className="px-2 py-2 text-center tabular-nums"
                      style={pri != null ? priorityHeatStyle(pri) : undefined}
                      title={pri != null ? `우선순위 ${pri} · ${row}×${col}` : undefined}
                    >
                      {formatDisplayValue(val)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">
        행=<span className="font-semibold text-slate-800">주모델 등급</span>
        {" · "}
        열=보조모델 등급
        {heatByPriority ? " · 색이 진할수록 점검 우선순위 높음(1→16)" : null}
      </p>
    </div>
  );
}

export function DataTable({
  rows,
  columns,
  empty = "데이터 없음",
  maxHeight,
}: {
  rows: Record<string, unknown>[];
  columns?: string[];
  empty?: string;
  maxHeight?: number;
}) {
  const safeRows = Array.isArray(rows) ? rows : [];
  if (!safeRows.length) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  const first = safeRows[0];
  const cols =
    columns ||
    (first && typeof first === "object" && first !== null ? Object.keys(first) : []);
  if (!cols.length) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <div
      className="overflow-auto rounded-md border"
      style={maxHeight ? { maxHeight } : undefined}
    >
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-muted/80 backdrop-blur">
          <tr>
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2 text-left font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {safeRows.map((row, i) => (
            <tr key={i} className="border-t">
              {cols.map((c) => (
                <td key={c} className="whitespace-nowrap px-3 py-2 tabular-nums">
                  {formatDisplayValue(
                    row && typeof row === "object"
                      ? (row as Record<string, unknown>)[c] ?? ""
                      : "",
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DualMatrices({
  block,
}: {
  block?: {
    empty?: boolean;
    meta?: { total?: number; positive?: number };
    matrix_all?: MatrixPayload;
    matrix_pos?: MatrixPayload;
    positive_in_abc_pct?: number | null;
  } | null;
}) {
  if (!block || block.empty) return null;
  return (
    <div className="space-y-4">
      <div className="flex gap-6 text-sm">
        <div>
          <span className="text-muted-foreground">평가 전체 </span>
          <span className="font-semibold">{formatDisplayValue(block.meta?.total ?? 0)}</span>
        </div>
        <div>
          <span className="text-muted-foreground">실제 타겟=1 </span>
          <span className="font-semibold">{formatDisplayValue(block.meta?.positive ?? 0)}</span>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <MatrixTable matrix={block.matrix_all} title="(A) 평가 데이터 전체" />
        <MatrixTable matrix={block.matrix_pos} title="(B) 실제 타겟 분포" />
      </div>
      {block.positive_in_abc_pct != null && block.meta?.positive ? (
        <p className="text-xs text-muted-foreground">
          실제 타겟의 약 {formatDisplayValue(block.positive_in_abc_pct)}%가{" "}
          <span className="font-semibold text-slate-800">주A~주C</span> 구간에 포함됩니다.
        </p>
      ) : null}
    </div>
  );
}
