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
import { fmtFilingDate, fmtPct, fmtScore } from "@/lib/format";

type Point = {
  form?: string | null;
  filed?: string | null;
  ticker?: string;
  sentiment: number;
  income: number;
  revenue?: number | null;
};

export default function SentimentScatter({ points }: { points: Point[] }) {
  if (!points.length) {
    return <p className="muted">Not enough scored filings for a scatter yet.</p>;
  }
  return (
    <div className="chart-wrap chart-centerpiece">
      <div className="chart-quad-labels" aria-hidden="true">
        <span className="ql-top">Earnings improved</span>
        <span className="ql-bottom">Earnings declined</span>
        <span className="ql-left">More negative tone</span>
        <span className="ql-right">More positive tone</span>
      </div>
      <div className="chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 16, right: 20, bottom: 36, left: 16 }}>
            <CartesianGrid stroke="#ddd4c5" strokeDasharray="3 3" />
            <ReferenceLine y={0} stroke="#b8ae9c" />
            <ReferenceLine x={0} stroke="#b8ae9c" />
            <XAxis
              type="number"
              dataKey="sentiment"
              name="Tone"
              domain={[-1, 1]}
              tick={{ fontSize: 12, fill: "#6d6458" }}
              label={{ value: "MD&A tone", position: "bottom", offset: 12, fill: "#6d6458" }}
            />
            <YAxis
              type="number"
              dataKey="income"
              name="Earnings YoY %"
              tick={{ fontSize: 12, fill: "#6d6458" }}
              label={{
                value: "Net income YoY %",
                angle: -90,
                position: "insideLeft",
                style: { textAnchor: "middle", fill: "#6d6458" },
              }}
            />
            <ZAxis range={[90, 90]} />
            <Tooltip
              content={({ payload }) => {
                const p = payload?.[0]?.payload as Point | undefined;
                if (!p) return null;
                return (
                  <div className="chart-tooltip">
                    {p.ticker ? <div className="tip-strong">{p.ticker}</div> : null}
                    <div>
                      {p.form} · {fmtFilingDate(p.filed)}
                    </div>
                    <div>Tone {fmtScore(p.sentiment)}</div>
                    <div>Net income YoY {p.income.toFixed(1)}%</div>
                    {p.revenue != null ? <div>Revenue YoY {fmtPct(p.revenue / 100)}</div> : null}
                  </div>
                );
              }}
            />
            <Scatter data={points} fill="#243b55" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
