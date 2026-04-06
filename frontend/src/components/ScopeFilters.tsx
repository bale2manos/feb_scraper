import type { ScopeMeta, ScopeState } from "../types";

type ScopeFiltersProps = {
  scope: ScopeState;
  meta: ScopeMeta;
  onChange: (nextScope: ScopeState) => void;
};

export function ScopeFilters({ scope, meta, onChange }: ScopeFiltersProps) {
  function updateField<K extends keyof ScopeState>(field: K, value: ScopeState[K]) {
    onChange({ ...scope, [field]: value });
  }

  return (
    <section className="panel">
      <h2>Scope</h2>
      <div className="form-grid">
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
        <label>
          Fases
          <select
            multiple
            value={scope.phases}
            onChange={(event) => updateField("phases", Array.from(event.target.selectedOptions).map((option) => option.value))}
          >
            {meta.phases.map((phase) => (
              <option key={phase} value={phase}>
                {phase}
              </option>
            ))}
          </select>
        </label>
        <label>
          Jornadas
          <select
            multiple
            value={scope.jornadas.map(String)}
            onChange={(event) =>
              updateField(
                "jornadas",
                Array.from(event.target.selectedOptions).map((option) => Number(option.value))
              )
            }
          >
            {meta.jornadas.map((jornada) => (
              <option key={jornada} value={jornada}>
                J{jornada}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
