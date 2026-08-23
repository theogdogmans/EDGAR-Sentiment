"use client";

import { useId, useState } from "react";
import MethodologyLink from "./MethodologyLink";

type Props = {
  active: boolean;
  compact?: boolean;
  /** Set false when nested inside a link (no nested buttons). */
  interactive?: boolean;
};

/**
 * Plain-English multiple-testing badge — never “FDR SIGNIFICANT” alone.
 * Meaning is always text; color is supplementary.
 */
export default function FdrBadge({ active, compact, interactive = true }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  if (!active) return null;

  const label = compact
    ? "Survives multiple-testing adjustment"
    : "Survives multiple-testing adjustment";

  if (!interactive) {
    return (
      <span
        className="fdr-badge fdr-badge-static"
        title="We tested hundreds of companies. Some relationships appear significant by chance. This badge means the relationship still stands out after adjusting for that."
      >
        <span className="fdr-badge-mark" aria-hidden="true">
          ✓
        </span>
        {label}
      </span>
    );
  }

  return (
    <span className={`fdr-badge${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="fdr-badge-btn"
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onBlur={() => setOpen(false)}
      >
        <span className="fdr-badge-mark" aria-hidden="true">
          ✓
        </span>
        {label}
      </button>
      <span role="tooltip" id={id} className="fdr-badge-tip" hidden={!open}>
        We tested hundreds of companies. Some relationships will appear significant by chance. This
        badge means the relationship still stands out after adjusting for that.{" "}
        <MethodologyLink topic="fdr">Read about FDR →</MethodologyLink>
      </span>
    </span>
  );
}
