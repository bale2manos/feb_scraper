import type {
  DependencyResponse,
  DependencySummary,
  GmResponse,
  ScopeMeta,
  ScopeState,
  TrendsResponse
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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

async function requestJson<T>(path: string, params: Record<string, string | number | string[] | number[] | undefined | null> = {}): Promise<T> {
  const query = buildQuery(params);
  const response = await fetch(`${API_BASE_URL}${path}${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar ${path}`);
  }
  return (await response.json()) as T;
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
  return {
    season: meta.selected.season || current.season || "",
    league: meta.selected.league || current.league || "",
    phases: meta.selected.phases || [],
    jornadas: meta.selected.jornadas || []
  };
}

export function getMeta(scope: Partial<ScopeState>) {
  return requestJson<ScopeMeta>("/meta/scopes", {
    season: scope.season,
    league: scope.league,
    phases: scope.phases,
    jornadas: scope.jornadas
  });
}

export function getGmPlayers(scope: ScopeState, mode: string) {
  return requestJson<GmResponse>("/gm/players", {
    season: scope.season,
    league: scope.league,
    phases: scope.phases,
    jornadas: scope.jornadas,
    mode
  });
}

export function getDependencyPlayers(scope: ScopeState) {
  return requestJson<DependencyResponse>("/dependency/players", {
    season: scope.season,
    league: scope.league,
    phases: scope.phases,
    jornadas: scope.jornadas
  });
}

export function getDependencySummary(scope: ScopeState, team: string, playerKey?: string | null) {
  return requestJson<DependencySummary>("/dependency/team-summary", {
    season: scope.season,
    league: scope.league,
    phases: scope.phases,
    jornadas: scope.jornadas,
    team,
    player_key: playerKey ?? undefined
  });
}

export function getPlayerTrends(scope: ScopeState, playerKey: string, window: number, metrics: string[]) {
  return requestJson<TrendsResponse>("/trends/player", {
    season: scope.season,
    league: scope.league,
    phases: scope.phases,
    jornadas: scope.jornadas,
    player_key: playerKey,
    window,
    metrics
  });
}

export function getTeamTrends(scope: ScopeState, team: string, window: number, metrics: string[]) {
  return requestJson<TrendsResponse>("/trends/team", {
    season: scope.season,
    league: scope.league,
    phases: scope.phases,
    jornadas: scope.jornadas,
    team,
    window,
    metrics
  });
}
