/**
 * Small, standalone helper functions shared by the chat page and the
 * dashboard — things like "how long ago was this," "is this column
 * full of numbers," and "which numeric columns are safe to chart
 * together." None of these talk to the backend; they just reshape
 * data that's already been fetched.
 */
// [OPS:FE-LIB-002] TableData
//
// What it does: the shape of a cited Excel chunk's table data, matching
// exactly what the backend's extract_table_chunks_from_xlsx_bytes()
// produces. Used by the chart-decision helpers below to figure out
// whether and how to render a cited chunk as a real chart instead of
// plain text.
export type TableData = { sheet: string; columns: string[]; rows: string[][] };

export function uid(): string {
  return Math.random().toString(36).slice(2);
}

export function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

// [OPS:FE-LIB-002b] formatRelativeTime()
//
// What it does: turns a timestamp into a rough phrase like "2 hours
// ago" or "3 days ago", for the "last synced" badge that shows how
// fresh the search index is. Deliberately imprecise — it's a freshness
// signal, not an exact log entry.
//
// Called by: page.tsx, to render the "Synced X ago" text.
export function formatRelativeTime(
  epochSeconds: number,
  now = Date.now(),
): string {
  const diffMs = now - epochSeconds * 1000;
  if (diffMs < 0) return "just now";

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;

  const months = Math.floor(days / 30);
  return `${months} month${months === 1 ? "" : "s"} ago`;
}

export function isNumeric(value: string): boolean {
  if (!value || !value.trim()) return false;
  return /^-?[\d,]+(\.\d+)?$/.test(value.trim());
}

export function toNumber(value: string): number {
  return Number(value.replace(/,/g, "")) || 0;
}

/** Decide which columns are numeric (>=70% of non-empty values parse as numbers). */
export function detectNumericColumns(table: TableData): boolean[] {
  return table.columns.map((_, colIdx) => {
    const values = table.rows.map((r) => r[colIdx]).filter((v) => v?.trim());
    if (values.length === 0) return false;
    const numericCount = values.filter(isNumeric).length;
    return numericCount / values.length >= 0.7;
  });
}

/**
 * Numeric columns are only safe to chart together when they're on a
 * comparable scale. Mixing a per-row amount with a cumulative running
 * balance (or a unit price with a total value) makes the smaller series
 * invisible. Drop "balance/running total"-style columns outright, then keep
 * only columns within ~20x of the largest remaining magnitude.
 */
export function selectChartableColumns(
  table: TableData,
  numericColIdxs: number[],
): number[] {
  const candidates = numericColIdxs.filter(
    (ci) => !/balance|running total/i.test(table.columns[ci]),
  );
  if (candidates.length === 0) return [];

  const magnitudes = candidates.map((ci) => ({
    ci,
    max: Math.max(...table.rows.map((r) => Math.abs(toNumber(r[ci])))),
  }));
  const overallMax = Math.max(...magnitudes.map((m) => m.max));
  if (overallMax === 0) return [];

  return magnitudes.filter((m) => m.max >= overallMax / 20).map((m) => m.ci);
}
