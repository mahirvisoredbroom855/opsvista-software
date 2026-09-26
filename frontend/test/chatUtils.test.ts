import assert from "node:assert/strict";
import { describe, it } from "mocha";
import {
  detectNumericColumns,
  formatRelativeTime,
  formatTime,
  isNumeric,
  selectChartableColumns,
  type TableData,
  toNumber,
  uid,
} from "../src/lib/chatUtils";

describe("uid", () => {
  it("returns distinct values across calls", () => {
    const a = uid();
    const b = uid();
    assert.notEqual(a, b);
    assert.ok(a.length > 0);
  });
});

describe("formatTime", () => {
  it("formats a timestamp as hour:minute", () => {
    const ts = new Date(2026, 0, 1, 9, 5).getTime();
    assert.match(formatTime(ts), /^\d{1,2}:\d{2}\s?(AM|PM)?$/i);
  });
});

describe("formatRelativeTime", () => {
  const now = new Date(2026, 0, 15, 12, 0, 0).getTime();

  it("reports seconds/sub-minute as 'just now'", () => {
    const epoch = (now - 30_000) / 1000;
    assert.equal(formatRelativeTime(epoch, now), "just now");
  });

  it("pluralizes minutes correctly", () => {
    const oneMinAgo = (now - 60_000) / 1000;
    const fiveMinAgo = (now - 5 * 60_000) / 1000;
    assert.equal(formatRelativeTime(oneMinAgo, now), "1 minute ago");
    assert.equal(formatRelativeTime(fiveMinAgo, now), "5 minutes ago");
  });

  it("switches to hours after 60 minutes", () => {
    const twoHoursAgo = (now - 2 * 3600_000) / 1000;
    assert.equal(formatRelativeTime(twoHoursAgo, now), "2 hours ago");
  });

  it("switches to days after 24 hours", () => {
    const threeDaysAgo = (now - 3 * 24 * 3600_000) / 1000;
    assert.equal(formatRelativeTime(threeDaysAgo, now), "3 days ago");
  });

  it("switches to months after 30 days", () => {
    const twoMonthsAgo = (now - 61 * 24 * 3600_000) / 1000;
    assert.equal(formatRelativeTime(twoMonthsAgo, now), "2 months ago");
  });

  it("treats future timestamps (clock skew) as 'just now'", () => {
    const future = (now + 60_000) / 1000;
    assert.equal(formatRelativeTime(future, now), "just now");
  });
});

describe("isNumeric", () => {
  it("accepts plain integers and decimals", () => {
    assert.equal(isNumeric("42"), true);
    assert.equal(isNumeric("3.14"), true);
  });

  it("accepts comma-separated thousands", () => {
    assert.equal(isNumeric("1,234,567"), true);
  });

  it("accepts negative numbers", () => {
    assert.equal(isNumeric("-99.5"), true);
  });

  it("rejects blank or non-numeric text", () => {
    assert.equal(isNumeric(""), false);
    assert.equal(isNumeric("   "), false);
    assert.equal(isNumeric("PO-76524"), false);
    assert.equal(isNumeric("Alpine Textiles Co."), false);
  });
});

describe("toNumber", () => {
  it("strips comma separators", () => {
    assert.equal(toNumber("1,234.50"), 1234.5);
  });

  it("falls back to 0 for non-numeric input", () => {
    assert.equal(toNumber("n/a"), 0);
  });
});

describe("detectNumericColumns", () => {
  it("flags a column numeric only when >=70% of values parse as numbers", () => {
    const table: TableData = {
      sheet: "Orders",
      columns: ["Buyer", "Quantity", "Notes"],
      rows: [
        ["Alpine Textiles", "25590", ""],
        ["NordicWear", "40758", "rush"],
        ["Heritage Apparel", "6004", ""],
      ],
    };
    assert.deepEqual(detectNumericColumns(table), [false, true, false]);
  });
});

describe("selectChartableColumns", () => {
  it("drops balance/running-total columns outright", () => {
    const table: TableData = {
      sheet: "Cash Book",
      columns: ["Date", "Debit", "Credit", "Running Balance"],
      rows: [
        ["2026-09-01", "500", "0", "500"],
        ["2026-09-02", "0", "300", "800"],
      ],
    };
    const numericIdxs = [1, 2, 3];
    assert.deepEqual(selectChartableColumns(table, numericIdxs), [1, 2]);
  });

  it("drops columns more than ~20x smaller than the largest remaining magnitude", () => {
    const table: TableData = {
      sheet: "Order Release Log",
      columns: ["Style", "Unit Price", "Quantity", "Total Value"],
      rows: [
        ["PTIL-WV-118", "3.28", "25590", "83935.20"],
        ["PTIL-KN-430", "3.30", "40758", "134501.40"],
      ],
    };
    const numericIdxs = [1, 2, 3];
    // Unit Price (~3.3) is >20x smaller than Total Value (~134501) and gets dropped;
    // Quantity (~40758) survives alongside Total Value.
    assert.deepEqual(selectChartableColumns(table, numericIdxs), [2, 3]);
  });

  it("returns an empty list when there are no numeric candidates", () => {
    const table: TableData = {
      sheet: "Empty",
      columns: ["Balance"],
      rows: [["100"]],
    };
    assert.deepEqual(selectChartableColumns(table, [0]), []);
  });
});
