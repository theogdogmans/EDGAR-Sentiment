"use client";

import { useId, useState } from "react";
import { TERM_DEFS } from "@/lib/explain";

type Props = {
  term: keyof typeof TERM_DEFS;
  children: React.ReactNode;
};

/** Accessible definition tip — works on hover and tap. */
export default function TermTip({ term, children }: Props) {
  const def = TERM_DEFS[term];
  const id = useId();
  const [open, setOpen] = useState(false);
  if (!def) return <>{children}</>;

  return (
    <span className={`term-tip${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="term-tip-trigger"
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setOpen(false)}
      >
        {children}
      </button>
      <span role="tooltip" id={id} className="term-tip-bubble" hidden={!open}>
        {def}
      </span>
    </span>
  );
}
