export type ScopeState = {
  season: string;
  league: string;
  phases: string[];
  jornadas: number[];
};

export type AuthSessionResponse = {
  authenticated: boolean;
  authRequired: boolean;
  ttlHours: number;
};

export type ScopeMeta = {
  seasons: string[];
  leagues: string[];
  phases: string[];
  jornadas: number[];
  selected: ScopeState;
  teams: TeamOption[];
  players: PlayerOption[];
};

export type PlayerOption = {
  playerKey: string;
  label: string;
  name: string;
  team: string;
  dorsal?: string | null;
  gamesPlayed: number;
};

export type TeamOption = {
  name: string;
  gamesPlayed: number;
};

export type GmResponse = {
  scope: ScopeState;
  mode: string;
  columns: string[];
  rows: Record<string, unknown>[];
  players: PlayerOption[];
};

export type DependencyResponse = {
  scope: ScopeState;
  rows: Record<string, unknown>[];
  teams: TeamOption[];
  players: PlayerOption[];
};

export type DependencySummary = {
  scope: ScopeState;
  selectedTeam: string | null;
  selectedPlayerKey?: string | null;
  structuralRisk: string;
  metrics: Record<string, number | string>;
  detail: {
    playerKey: string;
    name: string;
    image: string;
    team: string;
    birthYear?: number | null;
    gamesPlayed: number;
    risk: string;
    focus: string;
    dependencyScore: number;
    usageShare: number;
    scoringShare: number;
    creationShare: number;
    reboundShare: number;
    clutchShare: number | null;
    hasClutchData: boolean;
    diagnosis: string;
  } | null;
  tableRows: Record<string, unknown>[];
  note: string;
};

export type TrendSummaryRow = {
  metric: string;
  recent_avg: number;
  scope_avg: number;
  delta: number;
};

export type TrendsResponse = {
  scope: ScopeState;
  selectedPlayerKey?: string | null;
  selectedTeam?: string | null;
  availableMetrics: { key: string; label: string }[];
  selectedMetrics: string[];
  window: number;
  windowMax: number;
  recentCount: number;
  summaryRows: TrendSummaryRow[];
  recentGames: Record<string, unknown>[];
  chartRows: Record<string, unknown>[];
  players?: PlayerOption[];
  teams?: TeamOption[];
};

export type SimilarityCandidate = {
  playerKey: string;
  label: string;
  name: string;
  team: string;
  image: string;
  gamesPlayed: number;
  minutes: number;
  points: number;
  rebounds: number;
  assists: number;
  usg: number;
  similarityScore: number;
  focus: string;
  dependencyScore: number;
  reasons: string[];
  differences: string[];
};

export type SimilarityResponse = {
  scope: ScopeState;
  target: {
    playerKey: string;
    label: string;
    name: string;
    team: string;
    image: string;
    gamesPlayed: number;
    minutes: number;
    points: number;
    rebounds: number;
    assists: number;
    turnovers: number;
    usg: number;
    efg: number;
    astTo: number;
    focus: string;
    dependencyScore: number;
  } | null;
  filters: {
    minGames: number;
    minMinutes: number;
  };
  featureWeights: Record<string, number>;
  candidates: SimilarityCandidate[];
  players: PlayerOption[];
};

export type MarketPoolRow = {
  PLAYER_KEY: string;
  IMAGEN?: string;
  JUGADOR: string;
  EQUIPO: string;
  LIGA: string;
  "AÑO NACIMIENTO"?: number | null;
  PJ: number;
  MIN: number;
  PTS: number;
  REB: number;
  AST: number;
  TOV?: number;
  PLAYS?: number;
  "USG%"?: number;
  "TS%"?: number;
  "eFG%"?: number;
  PPP?: number;
  "AST/TO"?: number;
  "%PLAYS_EQUIPO"?: number;
  "%PUNTOS_EQUIPO"?: number;
  "%AST_EQUIPO"?: number;
  "%REB_EQUIPO"?: number;
  DEPENDENCIA_SCORE?: number;
  FOCO_PRINCIPAL?: string;
};

export type MarketPoolResponse = {
  season: string;
  rows: MarketPoolRow[];
  availableLeagues: string[];
  selectedLeagues: string[];
  summary: {
    playerCount: number;
    leagueCount: number;
    filters: {
      minGames: number;
      minMinutes: number;
      query: string;
    };
    leaders: {
      topScorer: string;
      topEfficiency: string;
      topDependency: string;
    };
  };
};

export type MarketComparePlayer = {
  playerKey: string;
  label: string;
  name: string;
  team: string;
  league: string;
  image: string;
  focus: string;
  dependencyScore: number;
};

export type MarketCompareMetricRow = {
  playerKey: string;
  value: number | string | null;
  formatted: string;
  percentile: number | null;
  deltaToBest: number | null;
  deltaToWorst: number | null;
};

export type MarketCompareMetric = {
  key: string;
  label: string;
  higherIsBetter: boolean | null;
  bestValue?: number;
  worstValue?: number;
  rows: MarketCompareMetricRow[];
};

export type MarketCompareBlock = {
  key: string;
  title: string;
  metrics: MarketCompareMetric[];
};

export type MarketCompareResponse = {
  season: string;
  players: MarketComparePlayer[];
  blocks: MarketCompareBlock[];
  percentiles: Record<string, Record<string, number | null>>;
  poolSummary: {
    totalPlayers: number;
    selectedPlayers: number;
    selectedPlayerKeys: string[];
  };
  availableLeagues: string[];
  selectedLeagues: string[];
};

export type MarketSuggestionCandidate = {
  playerKey: string;
  label: string;
  name: string;
  team: string;
  league: string;
  image: string;
  birthYear?: number | null;
  gamesPlayed: number;
  minutes: number;
  points: number;
  rebounds: number;
  assists: number;
  turnovers: number;
  plays: number;
  usg: number;
  ts: number;
  efg: number;
  ppp: number;
  astTo: number;
  dependencyScore: number;
  focus: string;
  similarityScore: number;
  reasons: string[];
  differences: string[];
};

export type MarketSuggestionsResponse = {
  season: string;
  availableLeagues: string[];
  selectedLeagues: string[];
  anchor: MarketSuggestionCandidate | null;
  candidates: MarketSuggestionCandidate[];
};

export type MarketOpportunityRow = {
  PLAYER_KEY: string;
  IMAGEN?: string;
  JUGADOR: string;
  EQUIPO: string;
  LIGA: string;
  "AÑO NACIMIENTO"?: number | null;
  PJ: number;
  MIN: number;
  "USG%": number;
  "TS%": number;
  "eFG%": number;
  PPP: number;
  "AST/TO": number;
  OpportunityScore: number;
  strengths: string[];
  blockers: string[];
  FOCO_PRINCIPAL?: string;
};

export type MarketOpportunityResponse = {
  season: string;
  availableLeagues: string[];
  selectedLeagues: string[];
  filters: {
    minGames: number;
    maxMinutes: number;
    maxUsg: number;
    query: string;
  };
  summary: {
    candidateCount: number;
    leaders: {
      topOpportunity: string;
      bestEfficiency: string;
    };
  };
  rows: MarketOpportunityRow[];
};

export type DatabaseSummaryResponse = {
  metrics: {
    scopes: number;
    jornadas: number;
    catalogedGames: number;
    withData: number;
    pending: number;
    failed: number;
  };
  scopeSummary: Record<string, unknown>[];
  jornadaSummary: Record<string, unknown>[];
  autoSyncTargets: Record<string, unknown>[];
  autoSync: {
    configPath: string;
    revalidateWindow: number;
    publish: boolean;
  };
};

export type ReportFile = {
  kind: "player" | "team" | "phase";
  fileName: string;
  fileUrl: string;
  previewUrl: string;
  mimeType: string;
  sizeBytes: number;
  generatedAt: string;
};

export type PlayerReportResponse = {
  scope: ScopeState;
  selectedTeam: string | null;
  selectedPlayerKey: string | null;
  playerName: string | null;
  playerLabel: string | null;
  report: ReportFile | null;
};

export type TeamReportResponse = {
  scope: ScopeState;
  selectedTeam: string | null;
  selectedPlayerKeys: string[];
  selectedPlayerNames: string[];
  rivalTeam: string | null;
  filters: {
    homeAway: string;
    h2hHomeAway: string;
    minGames: number;
    minMinutes: number;
    minShots: number;
  };
  report: ReportFile | null;
};

export type PhaseReportResponse = {
  scope: ScopeState;
  selectedTeams: string[];
  filters: {
    minGames: number;
    minMinutes: number;
    minShots: number;
  };
  report: ReportFile | null;
};

export type ReportBudgetResponse = {
  month: string;
  monthIso: string;
  monthlyTokens: number;
  consumedTokens: number;
  remainingTokens: number;
  percentRemaining: number;
  counts: {
    player: number;
    team: number;
    phase: number;
  };
  averageTokens: {
    player: number;
    team: number;
    phase: number;
  };
  estimatedReportsRemaining: {
    player: number;
    team: number;
    phase: number;
  };
  warningThresholdTokens: number;
  hardLimitTokens: number;
  isWarning: boolean;
  isBlocked: boolean;
  message: string | null;
  trackingMode: string;
  trackingEnabled: boolean;
  warning: string | null;
  lastUpdated: string | null;
};
