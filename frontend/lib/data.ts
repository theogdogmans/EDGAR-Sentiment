import { readFile } from "fs/promises";
import path from "path";
import { createSupabaseClient } from "./supabase";
import type { CompanyStat, ExampleFiling, PreloadStatus, SectorStat } from "./types";

export type SiteData = {
  source: "phase5_preview" | "supabase";
  companies: CompanyStat[];
  sectors: SectorStat[];
  examples: ExampleFiling[];
  preload: PreloadStatus | null;
};

function previewRoot(): string {
  // frontend/ cwd in Next → monorepo backend preview
  return path.join(process.cwd(), "..", "backend", "data", "phase5", "supabase_payload_preview");
}

export function isPreviewMode(): boolean {
  const v = (process.env.DATA_SOURCE || process.env.NEXT_PUBLIC_DATA_SOURCE || "").toLowerCase();
  return v === "phase5_preview" || v === "preview";
}

async function readJson<T>(file: string): Promise<T> {
  const raw = await readFile(path.join(previewRoot(), file), "utf8");
  return JSON.parse(raw) as T;
}

export async function loadSiteData(): Promise<SiteData> {
  if (isPreviewMode()) {
    const [companies, sectors, examples] = await Promise.all([
      readJson<CompanyStat[]>("companies.json"),
      readJson<SectorStat[]>("sectors.json"),
      readJson<ExampleFiling[]>("example_filings.json"),
    ]);
    return {
      source: "phase5_preview",
      companies,
      sectors,
      examples,
      preload: {
        running: false,
        stage: "preview",
        current: null,
        message: "Phase 5A local preview payload (not live Supabase).",
        coverage: {
          companies: companies.length,
          analyzed: companies.reduce((n, c) => n + (c.n_filings || 0), 0),
          ready: companies.filter((c) => (c.ranking_eligible_default ?? false)).length,
        },
      },
    };
  }

  const supabase = createSupabaseClient();
  const [{ data: sectors }, { data: companies }, { data: examples }, { data: preload }] =
    await Promise.all([
      supabase.from("sector_stats").select("*").order("sector"),
      supabase.from("company_stats").select("*").order("ticker"),
      supabase.from("example_filings").select("*"),
      supabase
        .from("preload_status")
        .select("running, stage, current, message, coverage")
        .eq("id", 1)
        .maybeSingle(),
    ]);

  return {
    source: "supabase",
    companies: (companies ?? []) as CompanyStat[],
    sectors: (sectors ?? []) as SectorStat[],
    examples: (examples ?? []) as ExampleFiling[],
    preload: (preload as PreloadStatus | null) ?? null,
  };
}

export async function loadCompany(ticker: string): Promise<{
  company: CompanyStat | null;
  examples: ExampleFiling[];
  source: SiteData["source"];
}> {
  const t = ticker.toUpperCase();
  if (isPreviewMode()) {
    const data = await loadSiteData();
    return {
      company: data.companies.find((c) => c.ticker === t) ?? null,
      examples: data.examples.filter((e) => e.ticker === t),
      source: data.source,
    };
  }
  const supabase = createSupabaseClient();
  const { data: company } = await supabase
    .from("company_stats")
    .select("*")
    .eq("ticker", t)
    .maybeSingle();
  const { data: examples } = await supabase
    .from("example_filings")
    .select("*")
    .eq("ticker", t)
    .order("filed", { ascending: false });
  return {
    company: (company as CompanyStat | null) ?? null,
    examples: (examples ?? []) as ExampleFiling[],
    source: "supabase",
  };
}

export async function loadExampleFiling(
  ticker: string,
  accession: string
): Promise<ExampleFiling | null> {
  if (isPreviewMode()) {
    const data = await loadSiteData();
    return (
      data.examples.find(
        (e) => e.ticker === ticker.toUpperCase() && e.accession === accession
      ) ?? null
    );
  }
  const supabase = createSupabaseClient();
  const { data } = await supabase
    .from("example_filings")
    .select("*")
    .eq("ticker", ticker.toUpperCase())
    .eq("accession", accession)
    .maybeSingle();
  return (data as ExampleFiling | null) ?? null;
}
