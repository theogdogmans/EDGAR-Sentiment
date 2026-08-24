"use client";

const SECTIONS = [
  { id: "research-question", label: "Research question" },
  { id: "data", label: "Data" },
  { id: "mda", label: "MD&A" },
  { id: "finbert", label: "Tone scoring (FinBERT)" },
  { id: "financial-data", label: "Financial data" },
  { id: "correlation", label: "Correlation" },
  { id: "agreement", label: "Agreement" },
  { id: "sample-size", label: "Sample size" },
  { id: "fdr", label: "Multiple testing (FDR)" },
  { id: "sector-weighting", label: "Sector weighting" },
  { id: "limitations", label: "Limitations" },
];

export default function MethodologyNav() {
  return (
    <>
      <nav className="meth-sticky" aria-label="Methodology sections">
        <div className="meth-sticky-title">On this page</div>
        <ul>
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`}>{s.label}</a>
            </li>
          ))}
        </ul>
      </nav>
      <label className="meth-jump">
        Jump to section{" "}
        <select
          aria-label="Jump to methodology section"
          defaultValue=""
          onChange={(e) => {
            const v = e.target.value;
            if (v) window.location.hash = v;
          }}
        >
          <option value="" disabled>
            Choose a section
          </option>
          {SECTIONS.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </label>
    </>
  );
}
