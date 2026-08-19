export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function fmtScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

export function fmtMoney(value: number | null | undefined, unit?: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const prefix = unit === "USD/shares" || unit === "USD / shares" ? "" : "$";
  if (unit && unit.toLowerCase().includes("share") && !unit.toLowerCase().includes("usd")) {
    return value.toFixed(2);
  }
  if (abs >= 1e12) return `${sign}${prefix}${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}${prefix}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${prefix}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${prefix}${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${prefix}${abs.toFixed(0)}`;
}

export function fmtR(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return value.toFixed(2);
}

export function toneClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (value > 0.02) return "pos";
  if (value < -0.02) return "neg";
  return "muted";
}
