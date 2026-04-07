import { useEffect, useMemo, useRef, useState } from "react";

import { SearchSelect } from "./SearchSelect";
import { useDebouncedValue, useLocalStorageState } from "../hooks";

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
  isLoading?: boolean;
  isUpdating?: boolean;
  storageKey?: string;
  stickyFirstColumn?: boolean;
  lockedLeadingColumns?: string[];
  defaultVisibleColumns?: string[];
};

type TableColumnPrefs = {
  order: string[];
  hidden: string[];
  widths: Record<string, number>;
};

type ResizeState = {
  column: string;
  startX: number;
  startWidth: number;
};

const DEFAULT_ROW_HEIGHT = 49;
const VIRTUALIZE_THRESHOLD = 40;
const VIRTUAL_OVERSCAN = 6;

function buildDefaultWidth(column: string) {
  if (column === "JUGADOR") {
    return 260;
  }
  if (column === "EQUIPO") {
    return 210;
  }
  if (column === "FOCO_PRINCIPAL") {
    return 180;
  }
  if (column.includes("%") || column.includes("SCORE")) {
    return 140;
  }
  return Math.min(Math.max(column.length * 10 + 38, 110), 240);
}

function clampWidth(width: number) {
  return Math.max(96, Math.min(Math.round(width), 420));
}

function buildDefaultOrder(columns: string[], lockedLeadingColumns: string[]) {
  const locked = lockedLeadingColumns.filter((column) => columns.includes(column));
  const remaining = columns.filter((column) => !locked.includes(column));
  return [...locked, ...remaining];
}

function normalizePrefs(rawValue: TableColumnPrefs | string[] | null | undefined, columns: string[], lockedLeadingColumns: string[]): TableColumnPrefs {
  const fallbackOrder = buildDefaultOrder(columns, lockedLeadingColumns);
  const rawOrder = Array.isArray(rawValue) ? rawValue : rawValue?.order ?? [];
  const rawHidden = Array.isArray(rawValue) ? [] : rawValue?.hidden ?? [];
  const rawWidths = Array.isArray(rawValue) ? {} : rawValue?.widths ?? {};

  const order = [...rawOrder.filter((column) => columns.includes(column))];
  fallbackOrder.forEach((column) => {
    if (!order.includes(column)) {
      order.push(column);
    }
  });

  const hidden = [...new Set(rawHidden.filter((column) => columns.includes(column) && !lockedLeadingColumns.includes(column)))];
  const widths = Object.fromEntries(
    Object.entries(rawWidths)
      .filter(([column, value]) => columns.includes(column) && Number.isFinite(Number(value)))
      .map(([column, value]) => [column, clampWidth(Number(value))])
  );
  return { order, hidden, widths };
}

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
  defaultSortColumn,
  isLoading = false,
  isUpdating = false,
  storageKey,
  stickyFirstColumn = false,
  lockedLeadingColumns = [],
  defaultVisibleColumns
}: DataTableProps) {
  const defaultColumnOrder = useMemo(() => buildDefaultOrder(columns, lockedLeadingColumns), [columns, lockedLeadingColumns]);
  const initialPrefs = useMemo<TableColumnPrefs>(() => {
    const normalizedVisible = (defaultVisibleColumns ?? []).filter((column) => columns.includes(column));
    const visibleSet = new Set([...lockedLeadingColumns, ...normalizedVisible]);
    const hidden = normalizedVisible.length
      ? defaultColumnOrder.filter((column) => !visibleSet.has(column) && !lockedLeadingColumns.includes(column))
      : [];
    return { order: defaultColumnOrder, hidden, widths: {} };
  }, [columns, defaultColumnOrder, defaultVisibleColumns, lockedLeadingColumns]);
  const storagePrefsKey = storageKey ? `table-columns:${storageKey}` : "__table-columns-disabled__";
  const [persistedPrefsRaw, setPersistedPrefsRaw] = useLocalStorageState<TableColumnPrefs | string[]>(storagePrefsKey, initialPrefs);
  const [showColumnEditor, setShowColumnEditor] = useState(false);
  const [sortColumn, setSortColumn] = useState<string>(defaultSortColumn ?? defaultColumnOrder[0] ?? "");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [searchValue, setSearchValue] = useState("");
  const [draggedColumn, setDraggedColumn] = useState<string | null>(null);
  const [dropTargetColumn, setDropTargetColumn] = useState<string | null>(null);
  const [columnToAdd, setColumnToAdd] = useState("");
  const [resizeState, setResizeState] = useState<ResizeState | null>(null);
  const [liveWidths, setLiveWidths] = useState<Record<string, number>>({});
  const [shellHeight, setShellHeight] = useState(620);
  const [scrollTop, setScrollTop] = useState(0);
  const debouncedSearchValue = useDebouncedValue(searchValue, 140);
  const shellRef = useRef<HTMLDivElement | null>(null);
  const liveWidthsRef = useRef<Record<string, number>>({});

  const persistedPrefs = useMemo(
    () => normalizePrefs(persistedPrefsRaw, columns, lockedLeadingColumns),
    [columns, lockedLeadingColumns, persistedPrefsRaw]
  );

  useEffect(() => {
    setLiveWidths(persistedPrefs.widths);
  }, [persistedPrefs.widths]);

  useEffect(() => {
    liveWidthsRef.current = liveWidths;
  }, [liveWidths]);

  useEffect(() => {
    if (!storageKey) {
      return;
    }
    const rawSignature = JSON.stringify(persistedPrefsRaw);
    const normalizedSignature = JSON.stringify(persistedPrefs);
    if (rawSignature !== normalizedSignature) {
      setPersistedPrefsRaw(persistedPrefs);
    }
  }, [persistedPrefs, persistedPrefsRaw, setPersistedPrefsRaw, storageKey]);

  const orderedColumns = persistedPrefs.order;
  const hiddenColumns = new Set(persistedPrefs.hidden);
  const visibleColumns = orderedColumns.filter((column) => !hiddenColumns.has(column));
  const movableColumns = orderedColumns.filter((column) => !lockedLeadingColumns.includes(column));
  const visibleMovableColumns = visibleColumns.filter((column) => !lockedLeadingColumns.includes(column));
  const hiddenMovableColumns = movableColumns.filter((column) => hiddenColumns.has(column));

  useEffect(() => {
    if (!shellRef.current || typeof ResizeObserver === "undefined") {
      return;
    }
    const shellElement = shellRef.current;
    const updateHeight = () => setShellHeight(shellElement.clientHeight || 620);
    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(shellElement);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!resizeState) {
      return;
    }
    const activeResize = resizeState;
    function handleMouseMove(event: MouseEvent) {
      const nextWidth = clampWidth(activeResize.startWidth + (event.clientX - activeResize.startX));
      setLiveWidths((current) => ({ ...current, [activeResize.column]: nextWidth }));
    }

    function handleMouseUp() {
      const nextWidth = liveWidthsRef.current[activeResize.column] ?? activeResize.startWidth;
      updatePrefs({
        order: persistedPrefs.order,
        hidden: persistedPrefs.hidden,
        widths: {
          ...persistedPrefs.widths,
          [activeResize.column]: nextWidth,
        },
      });
      setResizeState(null);
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [persistedPrefs.hidden, persistedPrefs.order, persistedPrefs.widths, resizeState]);

  useEffect(() => {
    if (!visibleColumns.length) {
      return;
    }
    if (!sortColumn || !visibleColumns.includes(sortColumn)) {
      setSortColumn(defaultSortColumn && visibleColumns.includes(defaultSortColumn) ? defaultSortColumn : visibleColumns[0]);
    }
  }, [defaultSortColumn, sortColumn, visibleColumns]);

  const normalizedSearch = debouncedSearchValue.trim().toLocaleLowerCase("es");
  const filteredRows = useMemo(
    () =>
      !normalizedSearch
        ? rows
        : rows.filter((row) =>
            visibleColumns.some((column) => String(row[column] ?? "").toLocaleLowerCase("es").includes(normalizedSearch))
          ),
    [normalizedSearch, rows, visibleColumns]
  );

  const sortedRows = useMemo(() => {
    if (!sortColumn) {
      return filteredRows;
    }
    return [...filteredRows].sort((left, right) => {
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
  }, [filteredRows, sortColumn, sortDirection]);

  const shouldVirtualize = !isLoading && sortedRows.length > VIRTUALIZE_THRESHOLD;
  const visibleWindowSize = Math.max(Math.ceil(shellHeight / DEFAULT_ROW_HEIGHT), 8);
  const virtualStartIndex = shouldVirtualize ? Math.max(Math.floor(scrollTop / DEFAULT_ROW_HEIGHT) - VIRTUAL_OVERSCAN, 0) : 0;
  const virtualEndIndex = shouldVirtualize ? Math.min(virtualStartIndex + visibleWindowSize + VIRTUAL_OVERSCAN * 2, sortedRows.length) : sortedRows.length;
  const visibleRows = shouldVirtualize ? sortedRows.slice(virtualStartIndex, virtualEndIndex) : sortedRows;
  const topSpacerHeight = shouldVirtualize ? virtualStartIndex * DEFAULT_ROW_HEIGHT : 0;
  const bottomSpacerHeight = shouldVirtualize ? Math.max((sortedRows.length - virtualEndIndex) * DEFAULT_ROW_HEIGHT, 0) : 0;

  function getColumnWidth(column: string) {
    return liveWidths[column] ?? persistedPrefs.widths[column] ?? buildDefaultWidth(column);
  }

  const totalTableWidth = visibleColumns.reduce((sum, column) => sum + getColumnWidth(column), 0);

  function updatePrefs(nextPrefs: TableColumnPrefs) {
    setPersistedPrefsRaw(normalizePrefs(nextPrefs, columns, lockedLeadingColumns));
  }

  function toggleSort(column: string) {
    if (sortColumn === column) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortColumn(column);
    setSortDirection(column === "JUGADOR" || column === "EQUIPO" ? "asc" : "desc");
  }

  function moveColumnToTarget(sourceColumn: string, targetColumn: string) {
    if (sourceColumn === targetColumn) {
      return;
    }
    const currentIndex = visibleMovableColumns.indexOf(sourceColumn);
    const targetIndex = visibleMovableColumns.indexOf(targetColumn);
    if (currentIndex < 0 || targetIndex < 0) {
      return;
    }
    const nextMovableColumns = [...visibleMovableColumns];
    const [removed] = nextMovableColumns.splice(currentIndex, 1);
    nextMovableColumns.splice(targetIndex, 0, removed);
    updatePrefs({
      order: [...lockedLeadingColumns, ...nextMovableColumns, ...hiddenMovableColumns],
      hidden: persistedPrefs.hidden,
      widths: persistedPrefs.widths,
    });
  }

  function hideColumn(column: string) {
    if (lockedLeadingColumns.includes(column)) {
      return;
    }
    if (hiddenColumns.has(column)) {
      return;
    }
    updatePrefs({ order: orderedColumns, hidden: [...persistedPrefs.hidden, column], widths: persistedPrefs.widths });
  }

  function showColumn(column: string) {
    if (!hiddenColumns.has(column)) {
      return;
    }
    updatePrefs({ order: orderedColumns, hidden: persistedPrefs.hidden.filter((item) => item !== column), widths: persistedPrefs.widths });
    setColumnToAdd("");
  }

  function resetColumns() {
    updatePrefs(initialPrefs);
  }

  function formatCell(value: unknown, row: Record<string, unknown>, column: string) {
    if (value == null || value === "") {
      return "--";
    }
    if (column === "JUGADOR") {
      const dorsal = row.DORSAL;
      const dorsalValue = dorsal == null || dorsal === "" ? "" : String(dorsal).trim();
      const dorsalText = dorsalValue ? `${dorsalValue.startsWith("#") ? dorsalValue : `#${dorsalValue}`} ` : "";
      return `${dorsalText}${String(value)}`.trim();
    }
    if (typeof value === "number") {
      if (Number.isInteger(value)) {
        return String(value);
      }
      return value.toFixed(Math.abs(value) >= 100 ? 1 : 2);
    }
    return String(value);
  }

  const skeletonRows = Array.from({ length: 6 }, (_, index) => `skeleton-${index}`);

  return (
    <section className="table-card">
      <div className="table-card-header">
        <div>
          {title ? <h3 className="table-title">{title}</h3> : null}
          {subtitle ? <p className="table-subtitle">{subtitle}</p> : null}
        </div>
        <div className="table-tools">
          {isUpdating ? <span className="status-badge">Actualizando</span> : null}
          <span className="table-count">
            {sortedRows.length} / {rows.length} filas
          </span>
          {storageKey ? (
            <button type="button" className={showColumnEditor ? "ghost-button is-active" : "ghost-button"} onClick={() => setShowColumnEditor((current) => !current)}>
              Columnas
            </button>
          ) : null}
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

      {showColumnEditor ? (
        <div className="column-editor">
          <div className="column-editor-header">
            <strong>Columnas visibles y orden</strong>
            <button type="button" className="ghost-button" onClick={resetColumns}>
              Reset
            </button>
          </div>

          {hiddenMovableColumns.length ? (
            <SearchSelect
              label="Anadir columna"
              options={hiddenMovableColumns.map((column) => ({ value: column, label: column }))}
              value={columnToAdd}
              onChange={(value) => {
                setColumnToAdd(value);
                showColumn(value);
              }}
              placeholder="Busca una columna para mostrar"
              suggestionLimit={null}
              showSelectionState={false}
            />
          ) : (
            <p className="detail-note">No hay mas columnas ocultas para anadir.</p>
          )}

          <div className="column-editor-grid">
            {lockedLeadingColumns.filter((column) => orderedColumns.includes(column)).map((column) => (
              <div key={column} className="column-chip is-locked">
                <div className="column-chip-main">
                  <span>{column}</span>
                  <small>Fija</small>
                </div>
              </div>
            ))}

            {visibleMovableColumns.map((column) => {
              const isDragging = draggedColumn === column;
              const isDropTarget = dropTargetColumn === column && draggedColumn !== column;

              return (
                <div
                  key={column}
                  draggable={true}
                  onDragStart={() => {
                    setDraggedColumn(column);
                    setDropTargetColumn(column);
                  }}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDropTargetColumn(column);
                  }}
                  onDragEnd={() => {
                    setDraggedColumn(null);
                    setDropTargetColumn(null);
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    if (draggedColumn) {
                      moveColumnToTarget(draggedColumn, column);
                    }
                    setDraggedColumn(null);
                    setDropTargetColumn(null);
                  }}
                  className={[
                    "column-chip",
                    isDragging ? "is-dragging" : "",
                    isDropTarget ? "is-drop-target" : ""
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <div className="column-chip-main">
                    <span>{column}</span>
                    <small>Visible</small>
                  </div>
                  <div className="column-chip-actions">
                    <button type="button" className="column-remove-button" onClick={() => hideColumn(column)} aria-label={`Quitar ${column}`}>
                      x
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {!visibleColumns.length ? (
        <div className="table-shell">
          <div className="table-empty">No hay columnas visibles. Activa alguna columna desde el editor.</div>
        </div>
      ) : (
        <div
          ref={shellRef}
          className={isUpdating ? "table-shell is-updating" : "table-shell"}
          onScroll={(event) => setScrollTop((event.currentTarget as HTMLDivElement).scrollTop)}
        >
          <table className="data-table" style={{ minWidth: `${totalTableWidth}px` }}>
            <thead>
              <tr>
                {visibleColumns.map((column, columnIndex) => (
                  <th
                    key={column}
                    className={stickyFirstColumn && columnIndex === 0 ? "sticky-cell sticky-cell-head" : undefined}
                    style={{ width: `${getColumnWidth(column)}px`, minWidth: `${getColumnWidth(column)}px` }}
                  >
                    <div className="table-header-shell">
                      <button className="table-sort" type="button" onClick={() => toggleSort(column)}>
                        {column}
                        <span className="table-sort-indicator">{sortColumn === column ? (sortDirection === "asc" ? "^" : "v") : "<>"}</span>
                      </button>
                      <div
                        className={resizeState?.column === column ? "table-column-resizer is-active" : "table-column-resizer"}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          setResizeState({
                            column,
                            startX: event.clientX,
                            startWidth: getColumnWidth(column),
                          });
                        }}
                        role="presentation"
                      />
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? skeletonRows.map((rowKey) => (
                    <tr key={rowKey} aria-hidden="true">
                      {visibleColumns.map((column, columnIndex) => (
                        <td key={`${rowKey}-${column}`} className={stickyFirstColumn && columnIndex === 0 ? "sticky-cell sticky-cell-body" : undefined}>
                          <span className="skeleton-line" />
                        </td>
                      ))}
                    </tr>
                  ))
                : null}

              {!isLoading && !sortedRows.length ? (
                <tr>
                  <td className="table-empty" colSpan={visibleColumns.length}>
                    {emptyMessage}
                  </td>
                </tr>
              ) : null}

              {!isLoading && shouldVirtualize && topSpacerHeight > 0 ? (
                <tr aria-hidden="true" className="table-spacer-row">
                  <td colSpan={visibleColumns.length} style={{ height: `${topSpacerHeight}px`, padding: 0, border: 0 }} />
                </tr>
              ) : null}

              {!isLoading
                ? visibleRows.map((row, index) => {
                    const absoluteIndex = shouldVirtualize ? virtualStartIndex + index : index;
                    const rowIdentity = String(row[idField] ?? row.PLAYER_KEY ?? row.PARTIDO ?? row.JUGADOR ?? index);
                    const rowKey = `${rowIdentity}-${absoluteIndex}`;
                    const isSelected = selectedKey != null && rowIdentity === selectedKey;

                    return (
                      <tr key={rowKey} className={isSelected ? "is-selected" : undefined} onClick={() => onSelect?.(row)}>
                        {visibleColumns.map((column, columnIndex) => (
                          <td
                            key={`${rowKey}-${column}`}
                            className={stickyFirstColumn && columnIndex === 0 ? "sticky-cell sticky-cell-body" : undefined}
                            style={{ width: `${getColumnWidth(column)}px`, minWidth: `${getColumnWidth(column)}px` }}
                          >
                            {formatCell(row[column], row, column)}
                          </td>
                        ))}
                      </tr>
                    );
                  })
                : null}

              {!isLoading && shouldVirtualize && bottomSpacerHeight > 0 ? (
                <tr aria-hidden="true" className="table-spacer-row">
                  <td colSpan={visibleColumns.length} style={{ height: `${bottomSpacerHeight}px`, padding: 0, border: 0 }} />
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
