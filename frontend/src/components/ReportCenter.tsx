import { useState } from "react";

import { buildApiUrl } from "../api";
import { useReports } from "../reports";

function formatFileSize(sizeBytes: number) {
  if (sizeBytes >= 1024 * 1024) {
    return `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`;
  }
  if (sizeBytes >= 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }
  return `${sizeBytes} B`;
}

export function ReportCenter() {
  const { jobs, clearFinishedJobs, closePreview, openPreview, previewJob, removeJob } = useReports();
  const [isOpen, setIsOpen] = useState(false);
  const pendingCount = jobs.filter((job) => job.status === "pending").length;
  const finishedJobs = jobs.filter((job) => job.status !== "pending");

  return (
    <>
      <div className="report-center-launcher">
        <button
          type="button"
          className={isOpen ? "report-center-toggle is-open" : "report-center-toggle"}
          onClick={() => setIsOpen((current) => !current)}
        >
          Informes
          {pendingCount ? <span className="report-center-count">{pendingCount}</span> : null}
        </button>

        {isOpen ? (
          <section className="report-center">
            <div className="report-center-header">
              <div>
                <span className="eyebrow">Informes</span>
                <h3>Centro de informes</h3>
                <p className="panel-copy">Las generaciones siguen activas aunque cambies de pagina.</p>
              </div>
              <div className="toolbar">
                {pendingCount ? <span className="status-badge">{pendingCount} en marcha</span> : null}
                {finishedJobs.length ? (
                  <button type="button" className="ghost-button" onClick={clearFinishedJobs}>
                    Limpiar
                  </button>
                ) : null}
              </div>
            </div>

            {jobs.length ? (
              <div className="report-center-list">
                {jobs.map((job) => (
                  <article key={job.id} className={`report-center-item is-${job.status}`}>
                    <div className="report-center-copy">
                      <strong>{job.title}</strong>
                      <span>{job.subtitle}</span>
                      {job.status === "success" && job.report ? (
                        <span>
                          {job.report.fileName} | {formatFileSize(job.report.sizeBytes)}
                        </span>
                      ) : null}
                      {job.status === "error" && job.error ? <span>{job.error}</span> : null}
                    </div>
                    <div className="report-center-actions">
                      {job.status === "pending" ? <span className="detail-note">Generando...</span> : null}
                      {job.status === "success" && job.report ? (
                        <>
                          <button type="button" className="ghost-button" onClick={() => openPreview(job.id)}>
                            Ver
                          </button>
                          <a className="ghost-button report-dock-link" href={buildApiUrl(job.report.fileUrl)} download={job.report.fileName}>
                            Descargar
                          </a>
                        </>
                      ) : null}
                      {job.status !== "pending" ? (
                        <button type="button" className="ghost-button" onClick={() => removeJob(job.id)}>
                          Quitar
                        </button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="detail-note">Todavia no has lanzado ningun informe.</p>
            )}
          </section>
        ) : null}
      </div>

      {previewJob?.report ? (
        <div className="report-modal-backdrop" role="presentation" onClick={closePreview}>
          <div
            className="report-modal"
            role="dialog"
            aria-modal="true"
            aria-label={previewJob.title}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="report-modal-header">
              <div>
                <span className="eyebrow">Vista previa</span>
                <h3>{previewJob.title}</h3>
                <p className="panel-copy">{previewJob.subtitle}</p>
              </div>
              <div className="toolbar">
                <a className="ghost-button report-dock-link" href={buildApiUrl(previewJob.report.fileUrl)} download={previewJob.report.fileName}>
                  Descargar
                </a>
                <button type="button" className="ghost-button" onClick={closePreview}>
                  Cerrar
                </button>
              </div>
            </div>

            <div className="report-modal-body">
              {previewJob.report.mimeType.startsWith("image/") ? (
                <img
                  className="report-modal-image"
                  src={buildApiUrl(previewJob.report.previewUrl)}
                  alt={previewJob.report.fileName}
                />
              ) : (
                <iframe
                  className="report-modal-frame"
                  src={buildApiUrl(previewJob.report.previewUrl)}
                  title={previewJob.report.fileName}
                />
              )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
