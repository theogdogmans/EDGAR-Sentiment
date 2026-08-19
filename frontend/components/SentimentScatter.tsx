"use client";

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

export default function SentimentScatter({
  points,
}: {
  points: { accession: string; form: string; filed: string; sentiment: number; income: number }[];
}) {
  if (!points.length) {
    return <p className="muted">Waiting for scored filings…</p>;
  }
  return (
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 8, right: 12, bottom: 12, left: 8 }}>
          <CartesianGrid stroke="#d7cdbc" />
          <XAxis
            type="number"
            dataKey="sentiment"
            name="Sentiment"
            domain={[-1, 1]}
            tick={{ fontSize: 12 }}
            label={{ value: "MD&A sentiment", position: "bottom", offset: 0 }}
          />
          <YAxis
            type="number"
            dataKey="income"
            name="Net income YoY %"
            tick={{ fontSize: 12 }}
            label={{ value: "Net income YoY %", angle: -90, position: "insideLeft" }}
          />
          <ZAxis range={[80, 80]} />
          <Tooltip
            formatter={(value: number, name: string) =>
              name === "Sentiment" ? value.toFixed(2) : `${value.toFixed(1)}%`
            }
          />
          <Scatter data={points} fill="#243b55" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
