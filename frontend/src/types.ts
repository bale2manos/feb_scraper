export type ScopeState = {
  season: string;
  league: string;
  phases: string[];
  jornadas: number[];
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
