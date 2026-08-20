export function sectorSlug(sector: string): string {
  return sector
    .trim()
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function findSectorBySlug<T extends { sector: string }>(
  sectors: T[],
  slug: string
): T | null {
  return sectors.find((s) => sectorSlug(s.sector) === slug) ?? null;
}
