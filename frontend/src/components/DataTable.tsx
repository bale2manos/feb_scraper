import { useEffect, useState } from "react";

type DataTableProps = {
  columns: string[];
  rows: Record<string, unknown>[];
  idField?: string;
  selectedKey?: string | null;
  onSelect?: (row: Record<string, unknown>) => void;
  title?: string;
  subtitle?: string;
  emptyMessage?: string;
  searchPlaceholder?: string;
  defaultSortColumn?: string;
};

export function DataTable({
  columns,
  rows,
  idField = "PLAYER_KEY",
  selectedKey,
  onSelect,
  title,
  subtitle,
  emptyMessage = "No hay filas para mostrar.",
  searchPlaceholder = "Buscar en la tabla",
  defaultSortColumn
}: DataTableProps) {
  const [sortColumn, setSortColumn] = useState<string>(defaultSortColumn ?? columns[0] ?? "");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [searchValue, setSearchValue] = useState("");

  useEffect(() => {
    if (!columns.length) {
      return;
    }
    if (!sortColumn || !columns.includes(sortColumn)) {
      setSortColumn(defaultSortColumn && columns.includes(defaultSortColumn) ? defaultSortColumn : columns[0]);
    }
  }, [columns, defaultSortColumn, sortColumn]);

  const normalizedSearch = searchValue.trim().toLocaleLowerCase("es");
  const filteredRows = !normalizedSearch
    ? rows
    : rows.filter((row) =>
        columns.some((column) => String(row[column] ?? "").toLocaleLowerCase("es").includes(normalizedSearch))
      );

  const sortedRows = [...filteredRows].sort((left, right) => {
    const leftValue = left[sortColumn];
    const rightValue = right[sortColumn];
    const leftNumber = Number(leftValue);
    const rightNumber = Number(rightValue);
    let comparison = 0;
    if (!Number.isNaN(leftNumber) && !Number.isNaN(rightNumber)) {
      comparison = leftNumber - rightNumber;
    } else {
      comparison = String(leftValue ?? "").localeCompare(String(rightValue ?? ""), "es");
    }
    return sortDirection === "asc" ? comparison : -comparison;
  });

  function toggleSort(column: string) {
    if (sortColumn === column) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortColumn(column);
    setSortDirection(column === "JUGADOR" ? "asc" : "desc");
  }

  function formatCell(value: unknown) {
    if (value == null || value === "") {
      return "—";
    }
    if (typeof value === "number") {
      if (Number.isInteger(value)) {
        return String(value);
      }
      return value.toFixed(Math.abs(value) >= 100 ? 1 : 2);
    }
    return String(value);
  }

  if (!columns.length) {
    return <p className="empty-state">No hay columnas para mostrar.</p>;
  }

  return (
    <section className="table-card">
      <div className="table-card-header">
        <div>
          {title ? <h3 className="table-title">{title}</h3> : null}
          {subtitle ? <p className="table-subtitle">{subtitle}</p> : null}
        </div>
        <div className="table-tools">
          <span className="table-count">
            {sortedRows.length} / {rows.length} filas
          </span>
          <input
            className="table-search"
            type="search"
            value={searchValue}
            onChange={(event) => setSearchValue(event.target.value)}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
          />
        </div>
      </div>
      <div className="table-shell">
        <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>
                <button className="table-sort" type="button" onClick={() => toggleSort(column)}>
                  {column}
                  <span className="table-sort-indicator">
                    {sortColumn === column ? (sortDirection === "asc" ? "↑" : "↓") : "↕"}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {!sortedRows.length ? (
            <tr>
              <td className="table-empty" colSpan={columns.length}>
                {emptyMessage}
              </td>
            </tr>
          ) : null}
          {sortedRows.map((row, index) => {
            const rowKey = String(row[idField] ?? row.JUGADOR ?? index);
            const isSelected = selectedKey != null && rowKey === selectedKey;
            return (
              <tr
                key={rowKey}
                className={isSelected ? "is-selected" : undefined}
                onClick={() => onSelect?.(row)}
              >
                {columns.map((column) => (
                  <td key={`${rowKey}-${column}`}>{formatCell(row[column])}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </section>
  );
}
