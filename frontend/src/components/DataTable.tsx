import { useState } from "react";

type DataTableProps = {
  columns: string[];
  rows: Record<string, unknown>[];
  idField?: string;
  selectedKey?: string | null;
  onSelect?: (row: Record<string, unknown>) => void;
};

export function DataTable({
  columns,
  rows,
  idField = "PLAYER_KEY",
  selectedKey,
  onSelect
}: DataTableProps) {
  const [sortColumn, setSortColumn] = useState<string>(columns[0] ?? "");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

  const sortedRows = [...rows].sort((left, right) => {
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

  if (!columns.length) {
    return <p className="empty-state">No hay columnas para mostrar.</p>;
  }

  return (
    <div className="table-shell">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>
                <button className="table-sort" type="button" onClick={() => toggleSort(column)}>
                  {column}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
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
                  <td key={`${rowKey}-${column}`}>{String(row[column] ?? "")}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
