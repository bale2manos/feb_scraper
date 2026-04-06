import { useState } from "react";

import type { ScopeMeta, ScopeState } from "../types";

type ScopeFiltersProps = {
  scope: ScopeState;
  meta: ScopeMeta;
  onChange: (nextScope: ScopeState) => void;
};

export function ScopeFilters({ scope, meta, onChange }: ScopeFiltersProps) {
  const [showAllPhases, setShowAllPhases] = useState(false);
  const [showAllJornadas, setShowAllJornadas] = useState(false);

  function updateField<K extends keyof ScopeState>(field: K, value: ScopeState[K]) {
    onChange({ ...scope, [field]: value });
  }

  function toggleStringValue(field: "phases", value: string) {
    const currentValues = scope[field];
    const nextValues = currentValues.includes(value)
      ? currentValues.filter((item) => item !== value)
      : [...currentValues, value];
    updateField(field, nextValues);
  }

  function toggleNumberValue(field: "jornadas", value: number) {
    const currentValues = scope[field];
    const nextValues = currentValues.includes(value)
      ? currentValues.filter((item) => item !== value)
      : [...currentValues, value].sort((left, right) => left - right);
    updateField(field, nextValues);
  }

  const visiblePhases = showAllPhases ? meta.phases : meta.phases.slice(0, 6);
  const visibleJornadas = showAllJornadas ? meta.jornadas : meta.jornadas.slice(0, 12);

  return (
    <section className="panel scope-panel">
      <div className="scope-header">
        <div>
          <span className="eyebrow">Filtros base</span>
          <h2>Scope</h2>
          <p className="panel-copy">Misma idea analitica, pero con una navegacion mas rapida y visual para moverse por temporada, liga y tramos de competicion.</p>
        </div>
        <div className="scope-summary">
          <span className="scope-badge">{scope.season || "Sin temporada"}</span>
          <span className="scope-badge">{scope.league || "Sin liga"}</span>
          <span className="scope-badge">{scope.phases.length} fases</span>
          <span className="scope-badge">{scope.jornadas.length} jornadas</span>
        </div>
      </div>
      <div className="form-grid scope-primary-grid">
        <label>
          Temporada
          <select value={scope.season} onChange={(event) => updateField("season", event.target.value)}>
            {meta.seasons.map((season) => (
              <option key={season} value={season}>
                {season}
              </option>
            ))}
          </select>
        </label>
        <label>
          Liga
          <select value={scope.league} onChange={(event) => updateField("league", event.target.value)}>
            {meta.leagues.map((league) => (
              <option key={league} value={league}>
                {league}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="scope-cluster">
        <div className="scope-cluster-header">
          <div>
            <h3>Fases</h3>
            <p className="panel-copy">Activa una o varias sin pelearte con un selector multiple clasico.</p>
          </div>
          <div className="scope-actions">
            <button type="button" className="ghost-button" onClick={() => updateField("phases", meta.phases)}>
              Todas
            </button>
            <button type="button" className="ghost-button" onClick={() => updateField("phases", [])}>
              Limpiar
            </button>
            {meta.phases.length > 6 ? (
              <button type="button" className="ghost-button" onClick={() => setShowAllPhases((current) => !current)}>
                {showAllPhases ? "Ver menos" : "Ver mas"}
              </button>
            ) : null}
          </div>
        </div>
        <div className="chip-grid">
          {visiblePhases.map((phase) => (
            <button
              key={phase}
              type="button"
              className={scope.phases.includes(phase) ? "filter-chip is-selected" : "filter-chip"}
              aria-pressed={scope.phases.includes(phase)}
              onClick={() => toggleStringValue("phases", phase)}
            >
              {phase}
            </button>
          ))}
        </div>
      </div>

      <div className="scope-cluster">
        <div className="scope-cluster-header">
          <div>
            <h3>Jornadas</h3>
            <p className="panel-copy">Seleccion rapida por chips, mas comoda en escritorio y bastante mejor en movil.</p>
          </div>
          <div className="scope-actions">
            <button type="button" className="ghost-button" onClick={() => updateField("jornadas", meta.jornadas)}>
              Todas
            </button>
            <button type="button" className="ghost-button" onClick={() => updateField("jornadas", [])}>
              Limpiar
            </button>
            {meta.jornadas.length > 12 ? (
              <button type="button" className="ghost-button" onClick={() => setShowAllJornadas((current) => !current)}>
                {showAllJornadas ? "Ver menos" : "Ver mas"}
              </button>
            ) : null}
          </div>
        </div>
        <div className="chip-grid chip-grid-jornadas">
          {visibleJornadas.map((jornada) => (
            <button
              key={jornada}
              type="button"
              className={scope.jornadas.includes(jornada) ? "filter-chip is-selected" : "filter-chip"}
              aria-pressed={scope.jornadas.includes(jornada)}
              onClick={() => toggleNumberValue("jornadas", jornada)}
            >
              J{jornada}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
