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

type Point = {
  form?: string | null;
  filed?: string | null;
  ticker?: string;
  sentiment: number;
  income: number;
};

export default function SentimentScatter({ points }: { points: Point[] }) {
  if (!points.length) {
    return <p className="muted">Not enough scored filings for a scatter yet.</p>;
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
            labelFormatter={() => ""}
            content={({ payload }) => {
              const p = payload?.[0]?.payload as Point | undefined;
              if (!p) return null;
              return (
                <div
                  style={{
                    background: "#fffaf1",
                    border: "1px solid #d7cdbc",
                    padding: "8px 10px",
                    fontSize: 12,
                  }}
                >
                  {p.ticker ? <div>{p.ticker}</div> : null}
                  <div>
                    {p.form} {p.filed}
                  </div>
                  <div>Sentiment {p.sentiment.toFixed(2)}</div>
                  <div>Net income {p.income.toFixed(1)}%</div>
                </div>
              );
            }}
          />
          <Scatter data={points} fill="#243b55" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
