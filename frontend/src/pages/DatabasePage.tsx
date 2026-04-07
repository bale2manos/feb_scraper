import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { getDatabaseSummary } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";

export function DatabasePage() {
  const summaryQuery = useQuery({
    queryKey: ["database-summary"],
    queryFn: ({ signal }) => getDatabaseSummary({ signal }),
    placeholderData: keepPreviousData
  });

  const data = summaryQuery.data ?? null;
  const error = summaryQuery.error instanceof Error ? summaryQuery.error.message : null;

  return (
    <div className="page-stack">
      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Cobertura</span>
            <h2>Base de datos</h2>
            <p className="panel-copy">Cobertura actual, detalle por jornadas y objetivos de autosync.</p>
          </div>
        </div>

        {summaryQuery.isLoading ? <p className="empty-state">Cargando estado de la base...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {data ? (
          <>
            <div className="metric-grid metric-grid-wide">
              <MetricCard label="Ambitos catalogados" value={String(data.metrics.scopes)} />
              <MetricCard label="Jornadas detectadas" value={String(data.metrics.jornadas)} />
              <MetricCard label="Partidos catalogados" value={String(data.metrics.catalogedGames)} />
              <MetricCard label="Con datos" value={String(data.metrics.withData)} />
              <MetricCard label="Pendientes" value={String(data.metrics.pending)} />
              <MetricCard label="Fallidos" value={String(data.metrics.failed)} />
            </div>

            <div className="insight-banner">
              <strong>Autosync semanal</strong>
              <span>
                {data.autoSync.publish ? "Publica cambios" : "No publica cambios"} | Revalida ultimas {data.autoSync.revalidateWindow} jornadas
              </span>
            </div>

            <DataTable
              title="Resumen por ambito"
              subtitle="Temporadas, ligas y fases ya catalogadas."
              columns={Object.keys(data.scopeSummary[0] ?? {})}
              rows={data.scopeSummary}
              idField="Temporada"
              defaultSortColumn="PartidosCatalogados"
              searchPlaceholder="Buscar temporada, liga o fase"
            />

            <DataTable
              title="Detalle por jornada"
              subtitle="Jornadas con datos, pendientes o fallidas."
              columns={Object.keys(data.jornadaSummary[0] ?? {})}
              rows={data.jornadaSummary}
              idField="Jornada"
              defaultSortColumn="Jornada"
              searchPlaceholder="Buscar jornada, liga o fase"
            />

            <DataTable
              title="Objetivos de autosync"
              subtitle={`Configuracion cargada desde ${data.autoSync.configPath}`}
              columns={Object.keys(data.autoSyncTargets[0] ?? {})}
              rows={data.autoSyncTargets}
              idField="Temporada"
              defaultSortColumn="Temporada"
              searchPlaceholder="Buscar objetivo"
              emptyMessage="No hay objetivos activos configurados para el autosync."
            />
          </>
        ) : null}
      </section>
    </div>
  );
}
