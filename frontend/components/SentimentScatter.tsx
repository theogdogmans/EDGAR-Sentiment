"use client";

import {
  CartesianGrid,
  ReferenceLine,
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
    <div className="chart-wrap">
      <div className="chart-axis-hint" aria-hidden="true">
        <span className="hint-left">More negative tone</span>
        <span className="hint-right">More positive tone</span>
      </div>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 12, right: 16, bottom: 28, left: 12 }}>
            <CartesianGrid stroke="#d7cdbc" strokeDasharray="3 3" />
            <ReferenceLine y={0} stroke="#b8ae9c" />
            <ReferenceLine x={0} stroke="#b8ae9c" />
            <XAxis
              type="number"
              dataKey="sentiment"
              name="Tone"
              domain={[-1, 1]}
              tick={{ fontSize: 12 }}
              label={{ value: "MD&A tone", position: "bottom", offset: 8 }}
            />
            <YAxis
              type="number"
              dataKey="income"
              name="Earnings YoY %"
              tick={{ fontSize: 12 }}
              label={{
                value: "Earnings change (YoY %)",
                angle: -90,
                position: "insideLeft",
                style: { textAnchor: "middle" },
              }}
            />
            <ZAxis range={[80, 80]} />
            <Tooltip
              formatter={(value: number, name: string) =>
                name === "Tone" ? value.toFixed(2) : `${value.toFixed(1)}%`
              }
              labelFormatter={() => ""}
              content={({ payload }) => {
                const p = payload?.[0]?.payload as Point | undefined;
                if (!p) return null;
                return (
                  <div className="chart-tooltip">
                    {p.ticker ? <div>{p.ticker}</div> : null}
                    <div>
                      {p.form} {p.filed}
                    </div>
                    <div>Tone {p.sentiment.toFixed(2)}</div>
                    <div>Net income {p.income.toFixed(1)}%</div>
                  </div>
                );
              }}
            />
            <Scatter data={points} fill="#243b55" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-axis-hint vertical-hints" aria-hidden="true">
        <span>Earnings improved ↑</span>
        <span>Earnings declined ↓</span>
      </div>
    </div>
  );
}
