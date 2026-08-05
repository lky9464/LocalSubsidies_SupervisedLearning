"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type PrCurvePayload = {
  recall: number[];
  precision: number[];
  pr_auc: number;
  baseline: number;
};

function buildChartData(curve: PrCurvePayload) {
  const n = Math.min(curve.recall.length, curve.precision.length);
  return Array.from({ length: n }, (_, i) => ({
    recall: curve.recall[i],
    precision: curve.precision[i],
  }));
}

export function PrCurveChart({ curve, label }: { curve: PrCurvePayload; label: string }) {
  const data = buildChartData(curve);

  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="recall"
            type="number"
            domain={[0, 1]}
            tickCount={6}
            tick={{ fontSize: 11 }}
            label={{ value: "Recall", position: "insideBottom", offset: -4, fontSize: 11 }}
          />
          <YAxis
            domain={[0, 1]}
            tickCount={6}
            tick={{ fontSize: 11 }}
            label={{ value: "Precision", angle: -90, position: "insideLeft", fontSize: 11 }}
          />
          <Tooltip
            formatter={(v: number) => [v.toFixed(4), "Precision"]}
            labelFormatter={(r) => `Recall ${Number(r).toFixed(4)}`}
          />
          <ReferenceLine
            y={curve.baseline}
            stroke="#94a3b8"
            strokeDasharray="4 4"
            label={{
              value: `baseline ${(curve.baseline * 100).toFixed(2)}%`,
              position: "insideTopRight",
              fontSize: 10,
            }}
          />
          <Line
            type="monotone"
            dataKey="precision"
            name={label}
            stroke="#2563eb"
            dot={false}
            strokeWidth={2}
          />
          <Legend />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-1 text-center text-sm font-medium">
        PR-AUC = {curve.pr_auc.toFixed(4)}
      </p>
    </div>
  );
}
