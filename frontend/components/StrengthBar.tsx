import { strengthBarWidth } from "@/lib/explain";

/** Visual strength of |ρ| — not a percentage score. */
export default function StrengthBar({
  rho,
  tone,
}: {
  rho: number | null | undefined;
  tone: "pos" | "neg" | "neutral";
}) {
  const w = Math.round(strengthBarWidth(rho) * 100);
  return (
    <div
      className={`strength-bar ${tone}`}
      role="img"
      aria-label={`Relationship strength indicator based on absolute Spearman ${rho ?? "n/a"}`}
    >
      <div className="strength-bar-track">
        <div className="strength-bar-fill" style={{ width: `${w}%` }} />
      </div>
    </div>
  );
}
