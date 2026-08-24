"use client";

type Point = { sentiment: number; income: number };

/** Tiny scatter preview for case-study cards; no axes, pattern only. */
export default function MiniScatter({ points }: { points: Point[] }) {
  if (!points.length) return <div className="mini-scatter empty" aria-hidden="true" />;

  const pad = 6;
  const w = 160;
  const h = 72;
  const xs = points.map((p) => p.sentiment);
  const ys = points.map((p) => p.income);
  const minX = Math.min(-0.3, ...xs);
  const maxX = Math.max(0.3, ...xs);
  const minY = Math.min(-20, ...ys);
  const maxY = Math.max(20, ...ys);
  const sx = (x: number) => pad + ((x - minX) / (maxX - minX || 1)) * (w - pad * 2);
  const sy = (y: number) => h - pad - ((y - minY) / (maxY - minY || 1)) * (h - pad * 2);
  const zx = sx(0);
  const zy = sy(0);

  return (
    <svg
      className="mini-scatter"
      viewBox={`0 0 ${w} ${h}`}
      width="100%"
      height={h}
      role="img"
      aria-label="Small preview of tone versus earnings change"
    >
      <line x1={pad} y1={zy} x2={w - pad} y2={zy} className="mini-axis" />
      <line x1={zx} y1={pad} x2={zx} y2={h - pad} className="mini-axis" />
      {points.map((p, i) => (
        <circle key={i} cx={sx(p.sentiment)} cy={sy(p.income)} r={2.2} className="mini-dot" />
      ))}
    </svg>
  );
}
