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
  trackingMode: string;
  trackingEnabled: boolean;
  warning: string | null;
  lastUpdated: string | null;
};
