import CompanyList from "@/components/CompanyList";
import { createSupabaseClient } from "@/lib/supabase";

export const revalidate = 30;

export default async function HomePage() {
  const supabase = createSupabaseClient();
  const [{ data: companies }, { data: preload }] = await Promise.all([
    supabase.from("companies").select("ticker, display, name, sector, filings_count, analyzed_count").order("ticker"),
    supabase.from("preload_status").select("running, stage, current, message, coverage").eq("id", 1).maybeSingle(),
  ]);

  const coverage = (preload?.coverage as { ready?: number; analyzed?: number; filings?: number } | null) ?? null;
  const rows = companies ?? [];
  const ready = rows.filter((r) => (r.analyzed_count || 0) >= 3).length;
  const analyzed = rows.reduce((n, r) => n + (r.analyzed_count || 0), 0);
  const filings = rows.reduce((n, r) => n + (r.filings_count || 0), 0);
  const progress = filings ? Math.min(100, Math.round((analyzed / filings) * 100)) : 0;

  return (
    <main className="hero">
      <div className="kicker">S&amp;P 500 · Supabase cache</div>
      <h1>Does the MD&A read like the statements?</h1>
      <p className="lede">
        Only S&amp;P 500 constituents. Preloaded filings and FinBERT scores live in Postgres so every
        lookup is a fast database read, not a live EDGAR scrape.
      </p>
      <section className="panel" style={{ marginTop: 24 }}>
        <h2>Preload</h2>
        <p className="hint">
          {preload?.running
            ? preload.message || "Working…"
            : preload?.stage === "done"
              ? "Cache is up to date."
              : preload?.message || "Waiting for the local worker to sync scores."}
        </p>
        <div className="progress">
          <div className="progress-bar" style={{ width: `${progress}%` }} />
        </div>
        <p className="note">
          {ready} companies ready · {analyzed}/{filings || "—"} filings scored
          {preload?.current ? ` · now ${preload.current}` : ""}
          {coverage?.ready != null ? "" : ""}
        </p>
      </section>
      <CompanyList companies={rows} />
    </main>
  );
}
