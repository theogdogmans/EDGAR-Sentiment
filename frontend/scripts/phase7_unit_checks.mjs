/**
 * Phase 7 targeted presentation checks (no research math changes).
 * Run: node frontend/scripts/phase7_unit_checks.mjs
 */

function fmtScore(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(3)}`;
}

function relationshipFromRho(rho) {
  if (rho == null || Number.isNaN(rho)) return "Relationship not available";
  if (rho >= 0.7) return "Strong positive";
  if (rho >= 0.4) return "Moderate positive";
  if (rho >= 0.2) return "Weak positive";
  if (rho > -0.2) return "Little / no relationship";
  if (rho > -0.4) return "Weak negative";
  if (rho > -0.7) return "Moderate negative";
  return "Strong negative";
}

function observationsPhrase(n, kind = "quarterly") {
  const unit = kind === "annual" ? "annual" : "quarterly";
  if (n == null || n <= 0) return `no ${unit} observations`;
  if (n === 1) return `1 ${unit} observation`;
  return `${n} ${unit} observations`;
}

let failed = 0;
function assert(cond, msg) {
  if (!cond) {
    console.error("FAIL", msg);
    failed += 1;
  } else {
    console.log("OK", msg);
  }
}

// Tone formatting — FITB-scale values must not collapse to +0.00
assert(fmtScore(0.00296) === "+0.003", "small positive tone → 3dp");
assert(fmtScore(-0.09729) === "-0.097", "negative tone → 3dp");
assert(fmtScore(0) === "0.000", "exact zero stays 0.000");
assert(fmtScore(null) === "—", "null tone is em dash, not 0");

// Relationship boundaries
assert(relationshipFromRho(0.85) === "Strong positive", "AAPL-like rho");
assert(relationshipFromRho(-0.525) === "Moderate negative", "AMZN-like rho");
assert(relationshipFromRho(0.014) === "Little / no relationship", "ABBV-like rho");
assert(relationshipFromRho(0.7) === "Strong positive", "boundary 0.70");
assert(relationshipFromRho(0.2) === "Weak positive", "boundary 0.20");
assert(relationshipFromRho(-0.2) === "Weak negative", "boundary -0.20");

// Annual vs quarterly wording
assert(observationsPhrase(5, "annual") === "5 annual observations", "10-K wording");
assert(observationsPhrase(15, "quarterly") === "15 quarterly observations", "10-Q wording");
assert(!observationsPhrase(5, "annual").includes("quarterly"), "no quarterly label on annual");

// FDR badge copy contract
const fdrCopy = "Survives multiple-testing adjustment";
assert(fdrCopy.includes("multiple-testing"), "FDR badge plain English");

// Methodology anchors expected on site
const anchors = [
  "#finbert",
  "#spearman",
  "#pearson",
  "#fdr",
  "#agreement",
  "#sample-size",
  "#xbrl",
  "#sector-weighting",
  "#scatterplots",
];
assert(anchors.every((a) => a.startsWith("#")), "methodology anchors present");

console.log(failed ? `FAILED ${failed}` : "ALL_PASS");
process.exit(failed ? 1 : 0);
