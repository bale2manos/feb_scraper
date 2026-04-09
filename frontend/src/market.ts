import type { ScopeState } from "./types";

const SHARED_SCOPE_STORAGE_KEY = "react-shared-scope";
const MARKET_SELECTED_LEAGUES_PREFIX = "react-market-selected-leagues-v1";
const MARKET_SHORTLIST_PREFIX = "react-market-shortlist-v1";
const MARKET_PENDING_INTENT_KEY = "react-market-pending-intent-v1";

type MarketIntent = {
  season: string;
  league: string;
  playerKey: string;
  source?: string;
};

function parseJson<T>(raw: string | null, fallback: T): T {
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function normalizeMarketLeagues(leagues: string[]) {
  const normalized: string[] = [];
  leagues.forEach((league) => {
    const text = String(league ?? "").trim();
    if (text && !normalized.includes(text)) {
      normalized.push(text);
    }
  });
  return normalized;
}

export function buildMarketSelectedLeaguesStorageKey(season: string) {
  return `${MARKET_SELECTED_LEAGUES_PREFIX}:${season || "default"}`;
}

export function buildMarketShortlistStorageKey(season: string, leagues: string[]) {
  const normalizedLeagues = normalizeMarketLeagues(leagues).sort((left, right) => left.localeCompare(right, "es"));
  return `${MARKET_SHORTLIST_PREFIX}:${season || "default"}:${normalizedLeagues.join("|") || "sin-liga"}`;
}

export function readSharedScopeFromStorage(): ScopeState {
  return parseJson<ScopeState>(window.localStorage.getItem(SHARED_SCOPE_STORAGE_KEY), {
    season: "",
    league: "",
    phases: [],
    jornadas: [],
  });
}

export function readMarketSelectedLeagues(season: string, fallbackLeague: string) {
  const stored = parseJson<string[]>(window.localStorage.getItem(buildMarketSelectedLeaguesStorageKey(season)), []);
  const normalized = normalizeMarketLeagues(stored);
  if (normalized.length) {
    return normalized;
  }
  return fallbackLeague ? [fallbackLeague] : [];
}

export function writeMarketSelectedLeagues(season: string, leagues: string[]) {
  window.localStorage.setItem(buildMarketSelectedLeaguesStorageKey(season), JSON.stringify(normalizeMarketLeagues(leagues)));
}

export function readMarketShortlist(season: string, leagues: string[]) {
  const stored = parseJson<string[]>(window.localStorage.getItem(buildMarketShortlistStorageKey(season, leagues)), []);
  return normalizeMarketLeagues(stored).slice(0, 6);
}

export function writeMarketShortlist(season: string, leagues: string[], playerKeys: string[]) {
  const normalizedKeys: string[] = [];
  playerKeys.forEach((playerKey) => {
    const text = String(playerKey ?? "").trim();
    if (text && !normalizedKeys.includes(text)) {
      normalizedKeys.push(text);
    }
  });
  window.localStorage.setItem(buildMarketShortlistStorageKey(season, leagues), JSON.stringify(normalizedKeys.slice(0, 6)));
}

export function addPlayerToMarketShortlist(season: string, leagues: string[], playerKey: string) {
  const normalizedPlayerKey = String(playerKey ?? "").trim();
  if (!season || !normalizedPlayerKey) {
    return [];
  }
  const current = readMarketShortlist(season, leagues);
  if (current.includes(normalizedPlayerKey)) {
    return current;
  }
  if (current.length >= 6) {
    return current;
  }
  const next = [...current, normalizedPlayerKey];
  writeMarketShortlist(season, leagues, next);
  return next;
}

export function removePlayerFromMarketShortlist(season: string, leagues: string[], playerKey: string) {
  const normalizedPlayerKey = String(playerKey ?? "").trim();
  const next = readMarketShortlist(season, leagues).filter((value) => value !== normalizedPlayerKey);
  writeMarketShortlist(season, leagues, next);
  return next;
}

export function queueMarketIntent(intent: MarketIntent) {
  if (!intent.season || !intent.league || !intent.playerKey) {
    return;
  }
  writeMarketSelectedLeagues(intent.season, [intent.league]);
  window.localStorage.setItem(MARKET_PENDING_INTENT_KEY, JSON.stringify(intent));
}

export function consumeMarketIntent(season: string) {
  const intent = parseJson<MarketIntent | null>(window.localStorage.getItem(MARKET_PENDING_INTENT_KEY), null);
  if (!intent || intent.season !== season) {
    return null;
  }
  window.localStorage.removeItem(MARKET_PENDING_INTENT_KEY);
  return intent;
}
