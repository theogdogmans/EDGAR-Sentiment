/**
 * Plain-English labels and copy helpers for Phase 6 clarity redesign.
 * Does not change underlying statistics; presentation only.
 */

export type RelationshipBand =
  | "strong_positive"
  | "moderate_positive"
  | "weak_positive"
  | "little"
  | "weak_negative"
  | "moderate_negative"
  | "strong_negative"
  | "unknown";

export type RelationshipLabel = {
  band: RelationshipBand;
  short: string;
  tone: "pos" | "neg" | "neutral";
};

/** Documented descriptive thresholds (Spearman ρ). Not economic importance. */
export function relationshipFromRho(rho: number | null | undefined): RelationshipLabel {
  if (rho == null || Number.isNaN(rho)) {
    return { band: "unknown", short: "Relationship not available", tone: "neutral" };
  }
  if (rho >= 0.7) return { band: "strong_positive", short: "Strong positive", tone: "pos" };
  if (rho >= 0.4) return { band: "moderate_positive", short: "Moderate positive", tone: "pos" };
  if (rho >= 0.2) return { band: "weak_positive", short: "Weak positive", tone: "pos" };
  if (rho > -0.2) return { band: "little", short: "Little or no relationship", tone: "neutral" };
  if (rho > -0.4) return { band: "weak_negative", short: "Weak negative", tone: "neg" };
  if (rho > -0.7) return { band: "moderate_negative", short: "Moderate negative", tone: "neg" };
  return { band: "strong_negative", short: "Strong negative", tone: "neg" };
}

export function sampleSizeLabel(n: number | null | undefined): string {
  if (n == null || n <= 0) return "Sample size not available";
  if (n >= 10) return "More established sample";
  if (n >= 8) return "Usable sample";
  if (n >= 6) return "Limited sample";
  return "Insufficient for rankings";
}

export function observationsPhrase(
  n: number | null | undefined,
  kind: "quarterly" | "annual" = "quarterly"
): string {
  const unit = kind === "annual" ? "annual" : "quarterly";
  if (n == null || n <= 0) return `no ${unit} observations`;
  if (n === 1) return `1 ${unit} observation`;
  return `${n} ${unit} observations`;
}

/** Map Spearman ρ to 0-1 for a restrained strength bar (not a percentage score). */
export function strengthBarWidth(rho: number | null | undefined): number {
  if (rho == null || Number.isNaN(rho)) return 0;
  return Math.min(1, Math.abs(rho));
}

export function agreementSentence(
  num: number | null | undefined,
  den: number | null | undefined
): string | null {
  if (num == null || den == null || den <= 0) return null;
  if (num === den) {
    return `Tone and earnings moved in the same direction in all ${den} comparable quarters.`;
  }
  return `Tone and earnings moved in the same direction in ${num} of ${den} comparable quarters.`;
}

export function companyTakeaway(
  name: string,
  rho: number | null | undefined,
  fdr: boolean
): string {
  const label = relationshipFromRho(rho);
  const who = name || "This company";
  let base: string;
  switch (label.band) {
    case "strong_positive":
    case "moderate_positive":
    case "weak_positive":
      base = `${who}'s management tone tended to become more positive when quarterly net income improved.`;
      break;
    case "strong_negative":
    case "moderate_negative":
    case "weak_negative":
      base = `${who} showed a negative relationship between management tone and quarterly net income.`;
      break;
    case "little":
      base = `${who} showed little relationship between MD&A tone and quarterly net income.`;
      break;
    default:
      base = `${who}: not enough data to summarize the tone and earnings relationship.`;
  }
  if (fdr && label.tone !== "neutral") {
    return `${base} This relationship remained statistically notable after the multiple-testing adjustment.`;
  }
  return base;
}

export const TERM_DEFS: Record<string, string> = {
  mda: "Management's Discussion and Analysis, or MD&A, is the section where management explains company performance, trends, and risks.",
  finbert:
    "FinBERT is a language model trained for financial text. It estimates whether a sentence is positive, neutral, or negative.",
  spearman:
    "Spearman measures whether more positive tone generally appears alongside stronger financial performance. It focuses on direction and is less affected by unusually large earnings changes.",
  pearson:
    "Pearson measures the strength of a straight-line relationship. It is more sensitive than Spearman to unusually large changes in earnings.",
  fdr: "When hundreds of companies are tested, some can appear statistically notable by chance. False Discovery Rate, or FDR, adjusts for that problem.",
  yoy: "Year over year: compared with the same quarter one year earlier.",
  xbrl: "XBRL is structured financial data reported to the SEC.",
  agreement:
    "How often tone and earnings moved in the same direction, after excluding near-neutral cases.",
  "sample-size": "How many comparable quarterly filings enter the company relationship estimate.",
  "filing-weighted":
    "The filing-weighted result gives more influence to companies with more filings. It answers what a typical filing looks like.",
  "company-balanced":
    "The company-balanced result gives each company equal weight. It answers what a typical company looks like.",
};

export type MethodologyTopic =
  | "research-question"
  | "data"
  | "mda"
  | "finbert"
  | "sentiment-score"
  | "financial-data"
  | "xbrl"
  | "period-matching"
  | "correlation"
  | "spearman"
  | "pearson"
  | "agreement"
  | "sample-size"
  | "p-values"
  | "fdr"
  | "confidence-interval"
  | "sector-weighting"
  | "scatterplots"
  | "limitations"
  | "relationship-labels";

export const METHODOLOGY_HREF: Record<MethodologyTopic, string> = {
  "research-question": "/methodology#research-question",
  data: "/methodology#data",
  mda: "/methodology#mda",
  finbert: "/methodology#finbert",
  "sentiment-score": "/methodology#sentiment-score",
  "financial-data": "/methodology#financial-data",
  xbrl: "/methodology#xbrl",
  "period-matching": "/methodology#period-matching",
  correlation: "/methodology#correlation",
  spearman: "/methodology#spearman",
  pearson: "/methodology#pearson",
  agreement: "/methodology#agreement",
  "sample-size": "/methodology#sample-size",
  "p-values": "/methodology#p-values",
  fdr: "/methodology#fdr",
  "confidence-interval": "/methodology#confidence-interval",
  "sector-weighting": "/methodology#sector-weighting",
  scatterplots: "/methodology#scatterplots",
  limitations: "/methodology#limitations",
  "relationship-labels": "/methodology#relationship-labels",
};
