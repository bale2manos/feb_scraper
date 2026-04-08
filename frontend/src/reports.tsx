import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState } from "react";

import type { PhaseReportResponse, PlayerReportResponse, ReportFile, TeamReportResponse } from "./types";

export type ReportJobKind = "player" | "team" | "phase";
export type ReportJobStatus = "pending" | "success" | "error";
export type ReportJobResult = PlayerReportResponse | TeamReportResponse | PhaseReportResponse;

export type ReportJob = {
  id: string;
  taskKey: string;
  kind: ReportJobKind;
  title: string;
  subtitle: string;
  status: ReportJobStatus;
  startedAt: string;
  completedAt: string | null;
  error: string | null;
  report: ReportFile | null;
  result: ReportJobResult | null;
};

type StartReportJobParams<T extends ReportJobResult> = {
  taskKey: string;
  kind: ReportJobKind;
  title: string;
  subtitle: string;
  run: () => Promise<T>;
  getReport: (result: T) => ReportFile | null;
};

type ReportPreviewState = {
  taskId: string;
};

type ReportsContextValue = {
  jobs: ReportJob[];
  startReportJob: <T extends ReportJobResult>(params: StartReportJobParams<T>) => Promise<T>;
  getLatestJob: (taskKey: string) => ReportJob | null;
  removeJob: (jobId: string) => void;
  clearFinishedJobs: () => void;
  openPreview: (taskId: string) => void;
  closePreview: () => void;
  previewJob: ReportJob | null;
};

const ReportsContext = createContext<ReportsContextValue | null>(null);

function buildJobId() {
  return `job-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function toErrorMessage(error: unknown) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "No se ha podido generar el informe.";
}

function upsertJob(currentJobs: ReportJob[], nextJob: ReportJob) {
  const nextJobs = [nextJob, ...currentJobs.filter((job) => job.id !== nextJob.id && job.taskKey !== nextJob.taskKey)];
  return nextJobs.slice(0, 24);
}

export function buildScopeTaskKey(
  prefix: string,
  scope: { season: string; league: string; phases: string[]; jornadas: number[] },
  parts: Array<string | number | null | undefined>
) {
  const scopeKey = [scope.season, scope.league, scope.phases.join(","), scope.jornadas.join(",")].join("|");
  const suffix = parts
    .map((value) => String(value ?? ""))
    .map((value) => value.trim())
    .join("|");
  return `${prefix}::${scopeKey}::${suffix}`;
}

export function ReportsProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [jobs, setJobs] = useState<ReportJob[]>([]);
  const [previewState, setPreviewState] = useState<ReportPreviewState | null>(null);

  const startReportJob = useCallback(async <T extends ReportJobResult>(params: StartReportJobParams<T>) => {
    const startedAt = new Date().toISOString();
    const jobId = buildJobId();
    const pendingJob: ReportJob = {
      id: jobId,
      taskKey: params.taskKey,
      kind: params.kind,
      title: params.title,
      subtitle: params.subtitle,
      status: "pending",
      startedAt,
      completedAt: null,
      error: null,
      report: null,
      result: null
    };

    setJobs((current) => upsertJob(current, pendingJob));

    try {
      const result = await params.run();
      const completedJob: ReportJob = {
        ...pendingJob,
        status: "success",
        completedAt: new Date().toISOString(),
        report: params.getReport(result),
        result
      };
      setJobs((current) => upsertJob(current, completedJob));
      void queryClient.invalidateQueries({ queryKey: ["report-budget"] });
      return result;
    } catch (error) {
      const failedJob: ReportJob = {
        ...pendingJob,
        status: "error",
        completedAt: new Date().toISOString(),
        error: toErrorMessage(error)
      };
      setJobs((current) => upsertJob(current, failedJob));
      throw error;
    }
  }, [queryClient]);

  const getLatestJob = useCallback(
    (taskKey: string) => jobs.find((job) => job.taskKey === taskKey) ?? null,
    [jobs]
  );

  const removeJob = useCallback(
    (jobId: string) => {
      setJobs((current) => current.filter((job) => job.id !== jobId));
      setPreviewState((current) => (current?.taskId === jobId ? null : current));
    },
    [setJobs]
  );

  const clearFinishedJobs = useCallback(() => {
    setJobs((current) => current.filter((job) => job.status === "pending"));
    setPreviewState(null);
  }, []);

  const previewJob = useMemo(
    () => jobs.find((job) => job.id === previewState?.taskId) ?? null,
    [jobs, previewState]
  );

  const value = useMemo<ReportsContextValue>(
    () => ({
      jobs,
      startReportJob,
      getLatestJob,
      removeJob,
      clearFinishedJobs,
      openPreview: (taskId: string) => setPreviewState({ taskId }),
      closePreview: () => setPreviewState(null),
      previewJob
    }),
    [clearFinishedJobs, getLatestJob, jobs, previewJob, removeJob, startReportJob]
  );

  return <ReportsContext.Provider value={value}>{children}</ReportsContext.Provider>;
}

export function useReports() {
  const context = useContext(ReportsContext);
  if (!context) {
    throw new Error("useReports debe usarse dentro de ReportsProvider.");
  }
  return context;
}
