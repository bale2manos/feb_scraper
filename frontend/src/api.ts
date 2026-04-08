import type {
  AuthSessionResponse,
  DatabaseSummaryResponse,
  DependencyResponse,
  DependencySummary,
  GmResponse,
  PhaseReportResponse,
  PlayerReportResponse,
  ReportBudgetResponse,
  SimilarityResponse,
  ScopeMeta,
  ScopeState,
  TeamReportResponse,
  TrendsResponse
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

export class UnauthorizedError extends Error {
  constructor(message = "Sesion no valida o expirada.") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

type ApiRequestInit = RequestInit & {
  suppressUnauthorizedEvent?: boolean;
};

function buildQuery(params: Record<string, string | number | string[] | number[] | undefined | null>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value == null) {
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((item) => search.append(key, String(item)));
      return;
    }
    search.set(key, String(value));
  });
  return search.toString();
}

export function buildApiUrl(path: string) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

async function requestJson<T>(
  path: string,
  params: Record<string, string | number | string[] | number[] | undefined | null> = {},
  init: ApiRequestInit = {}
): Promise<T> {
  const query = buildQuery(params);
  const response = await fetch(`${API_BASE_URL}${path}${query ? `?${query}` : ""}`, {
    credentials: "include",
    ...init
  });
  if (response.status === 401) {
    if (!init.suppressUnauthorizedEvent) {
      window.dispatchEvent(new Event("feb-auth-unauthorized"));
    }
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar ${path}`);
  }
  return (await response.json()) as T;
}

async function requestPostJson<T>(path: string, body: object, init: ApiRequestInit = {}): Promise<T> {
  return requestJson<T>(
    path,
    {},
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(init.headers ?? {})
      },
      body: JSON.stringify(body),
      signal: init.signal,
      suppressUnauthorizedEvent: init.suppressUnauthorizedEvent
    }
  );
}

export function getAuthSession(init: ApiRequestInit = {}) {
  return requestJson<AuthSessionResponse>("/auth/session", {}, { ...init, suppressUnauthorizedEvent: true });
}

export function loginWithPassword(password: string, init: ApiRequestInit = {}) {
  return requestPostJson<AuthSessionResponse>("/auth/login", { password }, { ...init, suppressUnauthorizedEvent: true });
}

export function logout(init: ApiRequestInit = {}) {
  return requestPostJson<AuthSessionResponse>("/auth/logout", {}, { ...init, suppressUnauthorizedEvent: true });
}

export function emptyScopeMeta(): ScopeMeta {
  return {
    seasons: [],
    leagues: [],
    phases: [],
    jornadas: [],
    selected: { season: "", league: "", phases: [], jornadas: [] },
    teams: [],
    players: []
  };
}

export function normalizeScopeWithMeta(current: ScopeState, meta: ScopeMeta): ScopeState {
  const season = meta.seasons.includes(current.season) ? current.season : meta.selected.season || meta.seasons[0] || "";
  const league = meta.leagues.includes(current.league) ? current.league : meta.selected.league || meta.leagues[0] || "";

  const phases = current.phases.filter((phase) => meta.phases.includes(phase));
  const jornadas = current.jornadas.filter((jornada) => meta.jornadas.includes(jornada));

  return {
    season,
    league,
    phases: phases.length ? phases : meta.selected.phases || meta.phases,
    jornadas: jornadas.length ? jornadas : meta.selected.jornadas || meta.jornadas
  };
}

export function isScopeEqual(left: ScopeState, right: ScopeState) {
  return (
    left.season === right.season &&
    left.league === right.league &&
    left.phases.length === right.phases.length &&
    left.jornadas.length === right.jornadas.length &&
    left.phases.every((value, index) => value === right.phases[index]) &&
    left.jornadas.every((value, index) => value === right.jornadas[index])
  );
}

export function getMeta(scope: Partial<ScopeState>, init: RequestInit = {}) {
  return requestJson<ScopeMeta>(
    "/meta/scopes",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas
    },
    init
  );
}

export function getDatabaseSummary(init: RequestInit = {}) {
  return requestJson<DatabaseSummaryResponse>("/database/summary", {}, init);
}

export function getGmPlayers(scope: ScopeState, mode: string, init: RequestInit = {}) {
  return requestJson<GmResponse>(
    "/gm/players",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas,
      mode
    },
    init
  );
}

export function getDependencyPlayers(scope: ScopeState, init: RequestInit = {}) {
  return requestJson<DependencyResponse>(
    "/dependency/players",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas
    },
    init
  );
}

export function getDependencySummary(scope: ScopeState, team: string, playerKey?: string | null, init: RequestInit = {}) {
  return requestJson<DependencySummary>(
    "/dependency/team-summary",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas,
      team,
      player_key: playerKey ?? undefined
    },
    init
  );
}

export function getPlayerTrends(scope: ScopeState, playerKey: string, window: number, metrics: string[], init: RequestInit = {}) {
  return requestJson<TrendsResponse>(
    "/trends/player",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas,
      player_key: playerKey,
      window,
      metrics
    },
    init
  );
}

export function getTeamTrends(scope: ScopeState, team: string, window: number, metrics: string[], init: RequestInit = {}) {
  return requestJson<TrendsResponse>(
    "/trends/team",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas,
      team,
      window,
      metrics
    },
    init
  );
}

export function getPlayerSimilarity(
  scope: ScopeState,
  targetPlayerKey: string,
  minGames: number,
  minMinutes: number,
  init: RequestInit = {}
) {
  return requestJson<SimilarityResponse>(
    "/similarity/player",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas,
      target_player_key: targetPlayerKey,
      min_games: minGames,
      min_minutes: minMinutes
    },
    init
  );
}

export function generatePlayerReport(scope: ScopeState, team: string, playerKey: string, init: RequestInit = {}) {
  return requestPostJson<PlayerReportResponse>(
    "/reports/player",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas,
      team,
      playerKey
    },
    init
  );
}

export function generateTeamReport(
  scope: ScopeState,
  payload: {
    team: string;
    playerKeys: string[];
    rivalTeam: string;
    homeAway: string;
    h2hHomeAway: string;
    minGames: number;
    minMinutes: number;
    minShots: number;
  },
  init: RequestInit = {}
) {
  return requestPostJson<TeamReportResponse>(
    "/reports/team",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas,
      ...payload
    },
    init
  );
}

export function generatePhaseReport(
  scope: ScopeState,
  payload: {
    teams: string[];
    minGames: number;
    minMinutes: number;
    minShots: number;
  },
  init: RequestInit = {}
) {
  return requestPostJson<PhaseReportResponse>(
    "/reports/phase",
    {
      season: scope.season,
      league: scope.league,
      phases: scope.phases,
      jornadas: scope.jornadas,
      ...payload
    },
    init
  );
}

export function getReportBudget(init: RequestInit = {}) {
  return requestJson<ReportBudgetResponse>("/reports/budget", {}, init);
}
