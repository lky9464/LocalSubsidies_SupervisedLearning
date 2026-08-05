"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type ShapBarRow = {
  feature: string;
  feature_ko: string;
  importance_share: number;
  direction?: string;
  direction_label?: string;
  signed_share?: number;
  label?: string;
};

function rowLabel(r: ShapBarRow): string {
  const ko = r.feature_ko?.trim();
  if (ko && ko !== r.feature) return `${ko}`;
  return r.feature;
}

/** SHAP TOP10 — 기여비중(절대 크기)만 표시하는 일방향 가로 막대 */
export function ShapImportanceBarChart({ rows }: { rows: ShapBarRow[] }) {
  if (!rows.length) {
    return null;
  }

  const data = [...rows]
    .map((r) => ({
      ...r,
      label: rowLabel(r),
      abs_share: Math.abs(Number(r.importance_share) || 0),
    }))
    .sort((a, b) => b.abs_share - a.abs_share);

  const maxShare = Math.max(...data.map((d) => d.abs_share), 0.01);

  return (
    <div className="h-[360px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, maxShare * 1.08]}
            tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={120}
            tick={{ fontSize: 10 }}
          />
          <Tooltip
            formatter={(value: number) => [`${(value * 100).toFixed(2)}%`, "기여비중(절대)"]}
            labelFormatter={(label) => String(label)}
          />
          <Bar dataKey="abs_share" fill="#2563eb" radius={[0, 2, 2, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** @deprecated ShapImportanceBarChart 사용 */
export const ShapBidirectionalBarChart = ShapImportanceBarChart;
