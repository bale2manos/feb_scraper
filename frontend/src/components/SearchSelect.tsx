import { useEffect, useMemo, useRef, useState } from "react";

type SearchOption = {
  value: string;
  label: string;
};

type SearchSelectProps = {
  label: string;
  options: SearchOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  emptyText?: string;
  disabled?: boolean;
  suggestionLimit?: number | null;
  showSuggestionsOnlyWhenQuery?: boolean;
  showSelectionState?: boolean;
  emptySelectionText?: string;
};

export function SearchSelect({
  label,
  options,
  value,
  onChange,
  placeholder = "Buscar...",
  emptyText = "No hay coincidencias.",
  disabled = false,
  suggestionLimit = 12,
  showSuggestionsOnlyWhenQuery = false,
  showSelectionState = true,
  emptySelectionText = "Sin seleccion."
}: SearchSelectProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [query, setQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const selectedOption = options.find((option) => option.value === value) ?? null;
  const normalizedQuery = query.trim().toLocaleLowerCase("es");

  const filteredOptions = useMemo(() => {
    const matching = [...options]
      .filter((option) => option.label.toLocaleLowerCase("es").includes(normalizedQuery))
      .sort((left, right) => {
        const leftLabel = left.label.toLocaleLowerCase("es");
        const rightLabel = right.label.toLocaleLowerCase("es");
        const leftStarts = normalizedQuery ? leftLabel.startsWith(normalizedQuery) : false;
        const rightStarts = normalizedQuery ? rightLabel.startsWith(normalizedQuery) : false;
        if (leftStarts !== rightStarts) {
          return leftStarts ? -1 : 1;
        }
        return left.label.localeCompare(right.label, "es");
      });
    if (suggestionLimit == null) {
      return matching;
    }
    return matching.slice(0, suggestionLimit);
  }, [normalizedQuery, options, suggestionLimit]);

  function renderHighlightedLabel(labelText: string) {
    if (!normalizedQuery) {
      return labelText;
    }
    const lowerLabel = labelText.toLocaleLowerCase("es");
    const matchIndex = lowerLabel.indexOf(normalizedQuery);
    if (matchIndex < 0) {
      return labelText;
    }
    const matchEnd = matchIndex + normalizedQuery.length;
    return (
      <>
        {labelText.slice(0, matchIndex)}
        <mark className="search-match">{labelText.slice(matchIndex, matchEnd)}</mark>
        {labelText.slice(matchEnd)}
      </>
    );
  }

  useEffect(() => {
    setHighlightedIndex(0);
  }, [query, value]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  function selectNext(offset: number) {
    if (!filteredOptions.length) {
      return;
    }
    setHighlightedIndex((current) => {
      const nextValue = current + offset;
      if (nextValue < 0) {
        return filteredOptions.length - 1;
      }
      if (nextValue >= filteredOptions.length) {
        return 0;
      }
      return nextValue;
    });
  }

  function handleSelect(nextValue: string) {
    onChange(nextValue);
    setQuery("");
    setIsOpen(false);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      selectNext(1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setIsOpen(true);
      selectNext(-1);
      return;
    }
    if (event.key === "Escape") {
      setIsOpen(false);
      return;
    }
    if (event.key === "Enter" && filteredOptions[highlightedIndex]) {
      event.preventDefault();
      handleSelect(filteredOptions[highlightedIndex].value);
    }
  }

  const shouldShowSuggestions = isOpen && (!showSuggestionsOnlyWhenQuery || Boolean(query.trim()));

  return (
    <div ref={containerRef} className="search-select">
      <span className="search-multiselect-label">{label}</span>
      {showSelectionState ? (
        <div className="selected-chip-grid">
          {selectedOption ? (
            <span className="selected-chip selected-chip-static">{selectedOption.label}</span>
          ) : (
            <span className="detail-note">{emptySelectionText}</span>
          )}
        </div>
      ) : null}

      <div className="search-input-shell">
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsOpen(true)}
          onClick={() => setIsOpen(true)}
          placeholder={placeholder}
          aria-label={label}
          disabled={disabled}
        />
        {query ? (
          <button type="button" className="search-utility-button" onClick={() => setQuery("")}>
            Limpiar
          </button>
        ) : null}
      </div>

      {isOpen ? (
        <div className="suggestion-grid suggestion-panel">
          {!shouldShowSuggestions ? (
            <span className="detail-note">Escribe para ver opciones.</span>
          ) : filteredOptions.length ? (
            filteredOptions.map((option, index) => (
              <button
                key={option.value}
                type="button"
                className={
                  option.value === value
                    ? "filter-chip is-selected"
                    : index === highlightedIndex
                      ? "filter-chip is-highlighted"
                      : "filter-chip"
                }
                onClick={() => handleSelect(option.value)}
                onMouseEnter={() => setHighlightedIndex(index)}
                disabled={disabled}
              >
                {renderHighlightedLabel(option.label)}
              </button>
            ))
          ) : (
            <span className="detail-note">{emptyText}</span>
          )}
        </div>
      ) : null}
    </div>
  );
}
