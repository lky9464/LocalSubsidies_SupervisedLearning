"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type ScoreBinRow = {
  label: string;
  total: number;
  target: number;
};

/** 구간 내 Target 비중(target/total) 기준 적색 농도 — 0이면 흰색 */
export function targetBarFillByRate(target: number, total: number): string {
  if (total <= 0 || target <= 0) return "#ffffff";
  const rate = Math.min(1, Math.max(0, target / total));
  const lightness = 88 - rate * 48;
  const saturation = 50 + rate * 40;
  return `hsl(0, ${saturation}%, ${lightness}%)`;
}

function targetRatePct(target: number, total: number): string {
  if (total <= 0) return "0.0%";
  return `${((target / total) * 100).toFixed(1)}%`;
}

/** Y축 로그 스케일 tick — 1·2·5 × 10^n */
function logAxisTicks(max: number): number[] {
  if (max <= 0) return [1];
  const ticks: number[] = [];
  const ceiling = max * 1.05;
  for (let exp = 0; exp <= 12; exp++) {
    const base = 10 ** exp;
    if (base > ceiling) break;
    for (const m of [1, 2, 5]) {
      const v = m * base;
      if (v >= 1 && v <= ceiling) ticks.push(v);
    }
  }
  if (!ticks.includes(max)) ticks.push(max);
  return [...new Set(ticks)].sort((a, b) => a - b);
}

export function ScoreDistributionBarChart({ bins }: { bins: ScoreBinRow[] }) {
  if (!bins.length) return null;

  const maxTotal = Math.max(...bins.map((b) => b.total), 0);
  const minPositive = Math.min(...bins.map((b) => b.total).filter((t) => t > 0), Infinity);
  const useLogScale = maxTotal > 1 && Number.isFinite(minPositive) && maxTotal / minPositive >= 4;

  const data = bins.map((b) => ({
    ...b,
    targetRate: b.total > 0 ? b.target / b.total : 0,
    fill: targetBarFillByRate(b.target, b.total),
    stroke: b.target <= 0 ? "#e5e7eb" : undefined,
    /** 로그 축: 0은 null(막대 생략), 양수는 실제 건수 */
    totalPlot: useLogScale ? (b.total > 0 ? b.total : null) : b.total,
  }));

  const yDomain: [number, number | "auto"] = useLogScale ? [1, maxTotal] : [0, "auto"];
  const yTicks = useLogScale ? logAxisTicks(maxTotal) : undefined;

  return (
    <div className="h-[280px] w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9 }}
            angle={-35}
            textAnchor="end"
            height={56}
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            allowDecimals={false}
            scale={useLogScale ? "log" : "linear"}
            domain={yDomain}
            ticks={yTicks}
            tickFormatter={(v) => Number(v).toLocaleString()}
          />
          <Tooltip
            formatter={(value: number, name: string) => {
              if (name === "totalPlot" || name === "total") {
                return [Number(value).toLocaleString(), "전체 건수"];
              }
              return [value, name];
            }}
            labelFormatter={(label) => `구간 ${label}`}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const row = payload[0]?.payload as ScoreBinRow & { fill?: string };
              return (
                <div className="rounded-md border bg-background px-3 py-2 text-xs shadow">
                  <p className="font-medium">구간 {label}</p>
                  <p>전체: {row.total?.toLocaleString()}</p>
                  <p>Target: {row.target?.toLocaleString()}</p>
                  <p>Target 비중: {targetRatePct(row.target ?? 0, row.total ?? 0)}</p>
                </div>
              );
            }}
          />
          <Bar dataKey="totalPlot" name="totalPlot" radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.fill}
                stroke={entry.stroke || entry.fill}
                strokeWidth={entry.target <= 0 ? 1 : 0}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-1 text-center text-[10px] text-muted-foreground">
        막대 높이=전체 건수
        {useLogScale ? " (Y축 로그·최대 막대 기준)" : ""} · 색=Target 비중(구간 내 target÷total,
        높을수록 진함 · 0=흰색)
      </p>
    </div>
  );
}
