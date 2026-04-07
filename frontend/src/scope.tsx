import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect } from "react";

import { emptyScopeMeta, getMeta, isScopeEqual, normalizeScopeWithMeta } from "./api";
import { useLocalStorageState } from "./hooks";
import type { ScopeMeta, ScopeState } from "./types";

type ScopeContextValue = {
  scope: ScopeState;
  setScope: (value: ScopeState | ((current: ScopeState) => ScopeState)) => void;
};

const INITIAL_SCOPE: ScopeState = { season: "", league: "", phases: [], jornadas: [] };

const ScopeContext = createContext<ScopeContextValue | null>(null);

export function ScopeProvider({ children }: { children: React.ReactNode }) {
  const [scope, setScope] = useLocalStorageState<ScopeState>("react-shared-scope", INITIAL_SCOPE);

  return <ScopeContext.Provider value={{ scope, setScope }}>{children}</ScopeContext.Provider>;
}

export function useScope() {
  const context = useContext(ScopeContext);
  if (!context) {
    throw new Error("useScope debe usarse dentro de ScopeProvider.");
  }
  return context;
}

export function buildScopeQueryKey(scope: ScopeState) {
  return [scope.season, scope.league, scope.phases.join("|"), scope.jornadas.join("|")] as const;
}

export function useScopeMeta(): { meta: ScopeMeta; isLoading: boolean; isFetching: boolean } {
  const { scope, setScope } = useScope();
  const metaQuery = useQuery({
    queryKey: ["meta", ...buildScopeQueryKey(scope)],
    queryFn: ({ signal }) => getMeta(scope, { signal }),
    placeholderData: keepPreviousData
  });

  useEffect(() => {
    if (!metaQuery.data || metaQuery.isPlaceholderData) {
      return;
    }
    setScope((current) => {
      const next = normalizeScopeWithMeta(current, metaQuery.data);
      return isScopeEqual(current, next) ? current : next;
    });
  }, [metaQuery.data, metaQuery.isPlaceholderData, setScope]);

  return {
    meta: metaQuery.data ?? emptyScopeMeta(),
    isLoading: metaQuery.isLoading,
    isFetching: metaQuery.isFetching
  };
}
