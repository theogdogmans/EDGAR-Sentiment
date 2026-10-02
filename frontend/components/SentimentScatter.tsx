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
import { niYoyBaseEffectNote } from "@/lib/explain";
import { fmtFilingDate, fmtMoney, fmtPct, fmtScore } from "@/lib/format";

type Point = {
  form?: string | null;
  filed?: string | null;
  ticker?: string;
  sentiment: number;
  /** Plotted net income YoY in percentage points (capped ratio × 100 when a cap exists). */
  income: number;
  /** Uncapped net income YoY in percentage points. */
  incomeRaw?: number | null;
  revenue?: number | null;
  incomeCurrent?: number | null;
  incomePrior?: number | null;
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
                const rawPct = p.incomeRaw ?? p.income;
                const yoyRatio = rawPct / 100;
                const note = niYoyBaseEffectNote(yoyRatio, p.incomePrior, p.incomeCurrent);
                const capped = Math.abs(rawPct - p.income) > 0.05;
                return (
                  <div className="chart-tooltip">
                    {p.ticker ? <div className="tip-strong">{p.ticker}</div> : null}
                    <div>
                      {p.form} · {fmtFilingDate(p.filed)}
                    </div>
                    <div>Tone {fmtScore(p.sentiment)}</div>
                    <div>Net income YoY {rawPct.toFixed(1)}%</div>
                    {capped ? (
                      <div className="muted">
                        Chart position uses {p.income.toFixed(1)}%, the pooled cap for this form.
                      </div>
                    ) : null}
                    {p.incomePrior != null ? (
                      <div>Prior net income {fmtMoney(p.incomePrior)}</div>
                    ) : null}
                    {p.incomeCurrent != null ? (
                      <div>Current net income {fmtMoney(p.incomeCurrent)}</div>
                    ) : null}
                    {p.revenue != null ? <div>Revenue YoY {fmtPct(p.revenue / 100)}</div> : null}
                    {note ? <div className="muted">{note}</div> : null}
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
