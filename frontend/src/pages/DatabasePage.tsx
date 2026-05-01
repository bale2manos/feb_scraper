import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { buildApiUrl, getDatabaseSummary } from "../api";
import { DataTable } from "../components/DataTable";
import { MetricCard } from "../components/MetricCard";
import { ReportBudgetPanel } from "../components/ReportBudgetPanel";

function formatBytes(sizeBytes: number) {
  if (!sizeBytes) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = sizeBytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value >= 100 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Sin fecha";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("es-ES", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function kindLabel(kind: "player" | "team" | "phase") {
  if (kind === "player") {
    return "Jugador";
  }
  if (kind === "team") {
    return "Equipo";
  }
  return "Fase";
}

function issueBadgeClass(status: "ok" | "watch" | "warning") {
  return `status-badge status-${status}`;
}

export function DatabasePage() {
  const summaryQuery = useQuery({
    queryKey: ["database-summary"],
    queryFn: ({ signal }) => getDatabaseSummary({ signal }),
    placeholderData: keepPreviousData,
  });

  const data = summaryQuery.data ?? null;
  const error = summaryQuery.error instanceof Error ? summaryQuery.error.message : null;
  const scopeColumns = Object.keys(data?.scopeSummary[0] ?? {
    Temporada: "",
    Liga: "",
    Fase: "",
    JornadaMin: 0,
    JornadaMax: 0,
    JornadasDetectadas: 0,
    PartidosCatalogados: 0,
    ConDatos: 0,
    Pendientes: 0,
    Fallidos: 0,
    UltimaRevision: "",
    UltimoScrapeo: "",
  });
  const jornadaColumns = Object.keys(data?.jornadaSummary[0] ?? {
    Temporada: "",
    Liga: "",
    Fase: "",
    Jornada: 0,
    Partidos: 0,
    ConDatos: 0,
    Pendientes: 0,
    Fallidos: 0,
  });
  const autosyncColumns = Object.keys(data?.autoSyncTargets[0] ?? {
    Temporada: "",
    Liga: "",
    Fases: "",
    Jornadas: "",
  });

  return (
    <div className="page-stack">
      <section className="panel page-panel">
        <div className="page-header">
          <div>
            <span className="eyebrow">Centro de control</span>
            <h2>Dashboard operativo</h2>
            <p className="panel-copy">
              Cobertura, salud de datos, estado cloud y biblioteca local para seguir avanzando sin relanzar el sync completo.
            </p>
          </div>
        </div>

        {summaryQuery.isLoading ? <p className="empty-state">Cargando centro de control...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {data ? (
          <>
            <div className="dashboard-hero-grid">
              <section className="panel panel-soft page-panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">Cobertura</span>
                    <h3 className="table-title">Estado de la base</h3>
                    <p className="table-subtitle">Foto rapida de catalogacion y trabajo pendiente.</p>
                  </div>
                  <span className={data.metrics.failed > 0 ? "status-badge status-warning" : "status-badge status-ok"}>
                    {data.metrics.failed > 0 ? "Con incidencias" : "Estable"}
                  </span>
                </div>

                <div className="metric-grid metric-grid-wide">
                  <MetricCard label="Ambitos" value={String(data.metrics.scopes)} />
                  <MetricCard label="Jornadas" value={String(data.metrics.jornadas)} />
                  <MetricCard label="Partidos catalogados" value={String(data.metrics.catalogedGames)} />
                  <MetricCard label="Con datos" value={String(data.metrics.withData)} />
                  <MetricCard label="Pendientes" value={String(data.metrics.pending)} />
                  <MetricCard label="Fallidos" value={String(data.metrics.failed)} />
                </div>

                <div className="insight-banner">
                  <strong>Autosync semanal</strong>
                  <span>
                    {data.autoSync.publish ? "Publica cambios cloud" : "Sin publish cloud"} | {data.autoSync.targetCount} objetivos activos | Revalida
                    ultimas {data.autoSync.revalidateWindow} jornadas
                  </span>
                </div>
              </section>

              <section className="panel panel-soft page-panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">Runtime</span>
                    <h3 className="table-title">Entorno actual</h3>
                    <p className="table-subtitle">Que SQLite estamos usando y como esta montado el modo actual.</p>
                  </div>
                  <span className={data.runtime.dbExists ? "status-badge status-ok" : "status-badge status-warning"}>
                    {data.runtime.sourceLabel}
                  </span>
                </div>

                <div className="dashboard-runtime-list">
                  <div className="dashboard-runtime-row">
                    <span>Entorno</span>
                    <strong>{data.runtime.environment}</strong>
                  </div>
                  <div className="dashboard-runtime-row">
                    <span>Storage app</span>
                    <strong>{data.runtime.appStorageMode}</strong>
                  </div>
                  <div className="dashboard-runtime-row">
                    <span>Storage informes</span>
                    <strong>{data.runtime.reportStorageMode}</strong>
                  </div>
                  <div className="dashboard-runtime-row">
                    <span>SQLite</span>
                    <strong>{formatBytes(data.runtime.dbSizeBytes)}</strong>
                  </div>
                  <div className="dashboard-runtime-row">
                    <span>Ultima actualizacion DB</span>
                    <strong>{formatDateTime(data.runtime.dbLastModified)}</strong>
                  </div>
                  {data.runtime.snapshotVersion ? (
                    <div className="dashboard-runtime-row">
                      <span>Snapshot version</span>
                      <strong>{data.runtime.snapshotVersion}</strong>
                    </div>
                  ) : null}
                </div>

                <p className="detail-note dashboard-path">{data.runtime.dbPath || "Ruta SQLite no disponible."}</p>

                <ReportBudgetPanel
                  budgetQuery={{
                    data: data.reportBudget,
                    isLoading: false,
                    isError: false,
                  }}
                />
              </section>
            </div>

            <div className="dashboard-split-grid">
              <section className="panel panel-soft page-panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">Calidad</span>
                    <h3 className="table-title">Salud de datos</h3>
                    <p className="table-subtitle">Coberturas utiles para scouting, clutch e informes.</p>
                  </div>
                </div>

                <div className="metric-grid metric-grid-wide">
                  <MetricCard label="Jugadores unicos" value={String(data.dataHealth.metrics.uniquePlayers)} />
                  <MetricCard label="Equipos unicos" value={String(data.dataHealth.metrics.uniqueTeams)} />
                  <MetricCard label="Partidos jugados" value={String(data.dataHealth.metrics.playedGames)} />
                  <MetricCard label="Asistencias raw" value={String(data.dataHealth.metrics.assistRows)} />
                </div>

                <div className="metric-grid metric-grid-wide">
                  <MetricCard
                    label="Bios con fecha"
                    value={`${data.dataHealth.coverage.birthDatePct.toFixed(1)}%`}
                    hint={`${data.dataHealth.metrics.playersMissingBirthDate} jugadores sin fecha`}
                  />
                  <MetricCard
                    label="Dorsales"
                    value={`${data.dataHealth.coverage.dorsalPct.toFixed(1)}%`}
                    hint={`${data.dataHealth.metrics.playersMissingDorsal} jugadores sin dorsal`}
                  />
                  <MetricCard
                    label="Boxscores jugados"
                    value={`${data.dataHealth.coverage.boxscorePct.toFixed(1)}%`}
                    hint={`${data.dataHealth.metrics.gamesWithoutBoxscore} partidos sin boxscore`}
                  />
                  <MetricCard
                    label="Partidos con clutch"
                    value={`${data.dataHealth.coverage.clutchGamesPct.toFixed(1)}%`}
                    hint="Informativo: solo mide donde ya existe muestra clutch"
                  />
                  <MetricCard
                    label="Lineups clutch"
                    value={`${data.dataHealth.coverage.lineupGamesPct.toFixed(1)}%`}
                    hint={`${data.dataHealth.metrics.clutchLineupRows} filas de lineup`}
                  />
                </div>

                <div className="dashboard-issue-list">
                  {data.dataHealth.issues.map((issue) => (
                    <article key={issue.key} className="dashboard-issue-row">
                      <div className="dashboard-issue-meta">
                        <strong>{issue.label}</strong>
                        <p>{issue.hint}</p>
                      </div>
                      <div className="dashboard-issue-value">
                        <span className={issueBadgeClass(issue.status)}>{issue.statusLabel}</span>
                        <strong>{issue.value}</strong>
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="panel panel-soft page-panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">Biblioteca</span>
                    <h3 className="table-title">Informes locales</h3>
                    <p className="table-subtitle">Lo ultimo generado y listo para revisar sin gastar presupuesto cloud.</p>
                  </div>
                  <span className="status-badge status-info">{data.reportLibrary.metrics.totalFiles} archivos</span>
                </div>

                <div className="metric-grid metric-grid-wide">
                  <MetricCard label="Total informes" value={String(data.reportLibrary.metrics.totalFiles)} />
                  <MetricCard label="Jugador" value={String(data.reportLibrary.metrics.playerFiles)} />
                  <MetricCard label="Equipo" value={String(data.reportLibrary.metrics.teamFiles)} />
                  <MetricCard label="Fase" value={String(data.reportLibrary.metrics.phaseFiles)} />
                  <MetricCard label="Peso total" value={formatBytes(data.reportLibrary.metrics.totalSizeBytes)} />
                </div>

                <div className="detail-note-block">
                  <strong>Ultimo generado</strong>
                  <span>{data.reportLibrary.metrics.latestFileName ?? "Todavia no hay informes generados en este entorno."}</span>
                  <span className="detail-note">{formatDateTime(data.reportLibrary.metrics.latestGeneratedAt)}</span>
                </div>

                {data.reportLibrary.recentFiles.length ? (
                  <div className="dashboard-report-list">
                    {data.reportLibrary.recentFiles.map((report) => (
                      <article key={`${report.kind}-${report.fileName}`} className="dashboard-report-card">
                        <div className="dashboard-report-meta">
                          <span className="status-badge status-info">{kindLabel(report.kind)}</span>
                          <strong>{report.fileName}</strong>
                          <p>
                            {formatDateTime(report.generatedAt)} | {formatBytes(report.sizeBytes)}
                          </p>
                        </div>
                        <div className="dashboard-report-actions">
                          <a
                            className="report-secondary-link"
                            href={buildApiUrl(report.previewUrl)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Abrir
                          </a>
                          <a className="report-link-button" href={buildApiUrl(report.fileUrl)} target="_blank" rel="noreferrer">
                            Descargar
                          </a>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="empty-state">Aun no hay informes locales en este entorno.</p>
                )}
              </section>
            </div>

            <DataTable
              title="Resumen por ambito"
              subtitle="Temporadas, ligas y fases ya catalogadas."
              columns={scopeColumns}
              rows={data.scopeSummary}
              idField="Temporada"
              defaultSortColumn="PartidosCatalogados"
              searchPlaceholder="Buscar temporada, liga o fase"
              storageKey="database-scope-summary"
            />

            <DataTable
              title="Detalle por jornada"
              subtitle="Jornadas con datos, pendientes o fallidas."
              columns={jornadaColumns}
              rows={data.jornadaSummary}
              idField="Jornada"
              defaultSortColumn="Jornada"
              searchPlaceholder="Buscar jornada, liga o fase"
              storageKey="database-jornada-summary"
            />

            <DataTable
              title="Objetivos de autosync"
              subtitle={`Configuracion cargada desde ${data.autoSync.configPath}`}
              columns={autosyncColumns}
              rows={data.autoSyncTargets}
              idField="Temporada"
              defaultSortColumn="Temporada"
              searchPlaceholder="Buscar objetivo"
              emptyMessage="No hay objetivos activos configurados para el autosync."
              storageKey="database-autosync-targets"
            />
          </>
        ) : null}
      </section>
    </div>
  );
}
