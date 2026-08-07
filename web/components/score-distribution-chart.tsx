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

/** Target 건수 기준 적색 농도 — 0이면 흰색 */
export function targetBarFill(target: number, maxTarget: number): string {
  if (target <= 0) return "#ffffff";
  if (maxTarget <= 0) return "#ffffff";
  const t = target / maxTarget;
  const lightness = 88 - t * 48;
  const saturation = 50 + t * 40;
  return `hsl(0, ${saturation}%, ${lightness}%)`;
}

export function ScoreDistributionBarChart({ bins }: { bins: ScoreBinRow[] }) {
  if (!bins.length) return null;

  const maxTarget = Math.max(...bins.map((b) => b.target), 0);
  const data = bins.map((b) => ({
    ...b,
    fill: targetBarFill(b.target, maxTarget),
    stroke: b.target <= 0 ? "#e5e7eb" : undefined,
  }));

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
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
          <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
          <Tooltip
            formatter={(value: number, name: string) => {
              if (name === "total") return [value.toLocaleString(), "전체 건수"];
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
                </div>
              );
            }}
          />
          <Bar dataKey="total" name="total" radius={[2, 2, 0, 0]}>
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
        막대 높이=전체 건수 · 색=Target 건수(모델 내 비교, 0=흰색)
      </p>
    </div>
  );
}
