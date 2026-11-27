/**
 * Display formatting only. Money arrives from the API as exact decimal strings ("1100.00")
 * and is formatted as text — it is never converted to a JavaScript number, so no binary
 * floating-point error can enter a displayed figure. All calculations happen in the backend.
 */

export function formatMoney(value: string | null | undefined, currency?: string): string {
  if (value === null || value === undefined || value === "") return "—";
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [whole, fraction = ""] = unsigned.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const text = fraction ? `${grouped}.${fraction}` : grouped;
  const prefix = currency ? `${currency} ` : "";
  return negative ? `−${prefix}${text}` : `${prefix}${text}`;
}

export function isZero(value: string | null | undefined): boolean {
  return !value || /^-?0*(\.0*)?$/.test(value);
}

export function isNegative(value: string | null | undefined): boolean {
  return !!value && value.startsWith("-") && !isZero(value);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Formats an ISO business date (YYYY-MM-DD) without timezone conversion. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  if (!y || !m || !d) return iso;
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const dt = new Date(iso);
  return dt.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  overdue: "Overdue",
  paid: "Paid",
  disputed: "Disputed",
  cancelled: "Cancelled",
  void: "Void",
  exception: "Needs review",
};

export const BUCKET_LABELS: Record<string, string> = {
  current: "Current",
  "1_30": "1–30 days",
  "31_60": "31–60 days",
  "61_90": "61–90 days",
  "91_plus": "90+ days",
};

export const ROW_STATUS_LABELS: Record<string, string> = {
  valid: "Ready",
  error: "Error",
  duplicate: "Already imported",
  amendment: "Changed — needs approval",
  needs_review: "Needs review",
  excluded: "Excluded",
  skipped: "Skipped",
  committed: "Imported",
  amendment_pending: "Amendment pending",
  amendment_approved: "Amendment approved",
  amendment_rejected: "Amendment rejected",
  duplicate_skipped: "Skipped (duplicate)",
  pending: "Not validated",
};
