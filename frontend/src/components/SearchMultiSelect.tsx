import { useEffect, useMemo, useRef, useState } from "react";

type SearchOption = {
  value: string;
  label: string;
};

type SearchMultiSelectProps = {
  label: string;
  options: SearchOption[];
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  emptyText?: string;
  suggestionLimit?: number | null;
  showSuggestionsOnlyWhenQuery?: boolean;
  emptySelectionText?: string;
};

export function SearchMultiSelect({
  label,
  options,
  values,
  onChange,
  placeholder = "Buscar...",
  emptyText = "No hay coincidencias.",
  suggestionLimit = 12,
  showSuggestionsOnlyWhenQuery = false,
  emptySelectionText = "Sin seleccion."
}: SearchMultiSelectProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [query, setQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const selectedOptions = options.filter((option) => values.includes(option.value));
  const normalizedQuery = query.trim().toLocaleLowerCase("es");

  const filteredOptions = useMemo(() => {
    const matching = [...options]
      .filter((option) => !values.includes(option.value))
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
  }, [normalizedQuery, options, suggestionLimit, values]);

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
  }, [query, values]);

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
    onChange([...values, nextValue]);
    setQuery("");
    setIsOpen(true);
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
    <div ref={containerRef} className="search-multiselect">
      <span className="search-multiselect-label">{label}</span>
      <div className="selected-chip-grid">
        {selectedOptions.length ? (
          selectedOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className="selected-chip"
              onClick={() => onChange(values.filter((value) => value !== option.value))}
            >
              {option.label}
              <span aria-hidden="true">x</span>
            </button>
          ))
        ) : (
          <span className="detail-note">{emptySelectionText}</span>
        )}
      </div>

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
                className={index === highlightedIndex ? "filter-chip is-highlighted" : "filter-chip"}
                onClick={() => handleSelect(option.value)}
                onMouseEnter={() => setHighlightedIndex(index)}
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
