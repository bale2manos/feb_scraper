export function asNumber(value: unknown) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

export function formatPercent(value: unknown) {
  return `${asNumber(value).toFixed(1)}%`;
}

export function formatNumber(value: unknown, digits = 1) {
  return asNumber(value).toFixed(digits);
}

export function getBirthYear(value: unknown) {
  const numeric = Number(value ?? NaN);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  const year = Math.trunc(numeric);
  if (year < 1900 || year > 2100) {
    return null;
  }
  return year;
}

export function getPlayerAge(value: unknown, referenceYear = new Date().getFullYear()) {
  const birthYear = getBirthYear(value);
  if (birthYear == null) {
    return null;
  }
  const age = referenceYear - birthYear;
  return age >= 0 && age <= 70 ? age : null;
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) {
    return;
  }
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(";"),
    ...rows.map((row) => headers.map((header) => `"${String(row[header] ?? "").replace(/"/g, "\"\"")}"`).join(";"))
  ].join("\n");

  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}
