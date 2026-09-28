/**
 * Small, standalone helper functions shared by the chat page and the
 * dashboard — things like "how long ago was this," "is this column
 * full of numbers," and "which numeric columns are safe to chart
 * together." None of these talk to the backend; they just reshape
 * data that's already been fetched.
 */
// [OPS:FE-LIB-002] Chat/dashboard helpers used by page.tsx [OPS:FE-CHAT] and
// dashboard/page.tsx [OPS:FE-DASH]. TableData mirrors the backend's
// metadata.table shape produced by [OPS:ING-001c]
// extract_table_chunks_from_xlsx_bytes() — a cited chunk's table field is
// passed straight through to detectNumericColumns()/selectChartableColumns()
// below to decide whether/how to render it as a chart instead of plain text.
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

/** "2 hours ago" / "3 days ago" style relative timestamp, for the index's
 * "last synced" badge — coarse on purpose, this is a freshness signal, not
 * a precise audit log entry. */
// [OPS:FE-LIB-002b] formatRelativeTime() — consumes file_info.modified_epoch
// from the backend's GET /index/status [OPS:CHAT-023] to render the "Synced
// X ago" badge.
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
