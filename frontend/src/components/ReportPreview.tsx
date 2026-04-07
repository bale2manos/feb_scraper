import { buildApiUrl } from "../api";
import type { ReportFile } from "../types";

type ReportPreviewProps = {
  title: string;
  subtitle: string;
  report: ReportFile | null;
  emptyMessage: string;
  isGenerating?: boolean;
  statusMessage?: string | null;
  onOpenFloating?: (() => void) | null;
};

function formatFileSize(sizeBytes: number) {
  if (sizeBytes >= 1024 * 1024) {
    return `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`;
  }
  if (sizeBytes >= 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }
  return `${sizeBytes} B`;
}

export function ReportPreview({
  title,
  subtitle,
  report,
  emptyMessage,
  isGenerating = false,
  statusMessage = null,
  onOpenFloating = null
}: ReportPreviewProps) {
  return (
    <section className="panel detail-panel report-preview-panel">
      <div className="detail-panel-header">
        <div>
          <span className="eyebrow">Informe</span>
          <h3>{title}</h3>
          <p className="panel-copy">{subtitle}</p>
        </div>
        {isGenerating ? <span className="status-badge">Generando</span> : null}
      </div>

      {report ? (
        <>
          <div className="report-toolbar">
            <div className="report-meta">
              <strong>{report.fileName}</strong>
              <span>
                {formatFileSize(report.sizeBytes)} | {report.generatedAt}
              </span>
            </div>
            <div className="report-link-group">
              {onOpenFloating ? (
                <button type="button" className="ghost-button" onClick={onOpenFloating}>
                  Ver flotante
                </button>
              ) : null}
              <a className="report-secondary-link" href={buildApiUrl(report.previewUrl)} target="_blank" rel="noreferrer">
                Abrir
              </a>
              <a className="report-link-button" href={buildApiUrl(report.fileUrl)} download={report.fileName}>
                Descargar
              </a>
            </div>
          </div>

          {report.mimeType.startsWith("image/") ? (
            <div
              className={onOpenFloating ? "report-preview-trigger is-clickable" : "report-preview-trigger"}
              onClick={() => onOpenFloating?.()}
              role={onOpenFloating ? "button" : undefined}
              tabIndex={onOpenFloating ? 0 : undefined}
              onKeyDown={(event) => {
                if (onOpenFloating && (event.key === "Enter" || event.key === " ")) {
                  event.preventDefault();
                  onOpenFloating();
                }
              }}
            >
              <img className="report-image" src={buildApiUrl(report.previewUrl)} alt={report.fileName} />
            </div>
          ) : (
            <div
              className={onOpenFloating ? "report-preview-trigger is-clickable" : "report-preview-trigger"}
              onClick={() => onOpenFloating?.()}
              role={onOpenFloating ? "button" : undefined}
              tabIndex={onOpenFloating ? 0 : undefined}
              onKeyDown={(event) => {
                if (onOpenFloating && (event.key === "Enter" || event.key === " ")) {
                  event.preventDefault();
                  onOpenFloating();
                }
              }}
            >
              <iframe className="report-frame" src={buildApiUrl(report.previewUrl)} title={report.fileName} />
            </div>
          )}
        </>
      ) : (
        <div className="detail-empty">
          <p className="empty-state">{isGenerating ? statusMessage || "Generando informe..." : emptyMessage}</p>
        </div>
      )}
    </section>
  );
}
