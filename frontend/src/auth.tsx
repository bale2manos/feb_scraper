import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { getAuthSession, loginWithPassword, logout, UnauthorizedError } from "./api";
import type { AuthSessionResponse } from "./types";

type AuthContextValue = {
  session: AuthSessionResponse;
  isLoading: boolean;
  isSubmitting: boolean;
  error: string | null;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
};

const DEFAULT_SESSION: AuthSessionResponse = {
  authenticated: false,
  authRequired: false,
  ttlHours: 12,
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const sessionQuery = useQuery({
    queryKey: ["auth-session"],
    queryFn: ({ signal }) => getAuthSession({ signal, suppressUnauthorizedEvent: true }),
    retry: false,
    staleTime: 60_000,
  });

  useEffect(() => {
    const handleUnauthorized = () => {
      queryClient.setQueryData<AuthSessionResponse>(["auth-session"], {
        authenticated: false,
        authRequired: true,
        ttlHours: sessionQuery.data?.ttlHours ?? DEFAULT_SESSION.ttlHours,
      });
    };
    window.addEventListener("feb-auth-unauthorized", handleUnauthorized);
    return () => window.removeEventListener("feb-auth-unauthorized", handleUnauthorized);
  }, [queryClient, sessionQuery.data?.ttlHours]);

  const login = async (password: string) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const nextSession = await loginWithPassword(password, { suppressUnauthorizedEvent: true });
      queryClient.setQueryData(["auth-session"], nextSession);
      await queryClient.invalidateQueries();
    } catch (nextError) {
      if (nextError instanceof UnauthorizedError) {
        setError("Contraseña incorrecta.");
      } else if (nextError instanceof Error) {
        setError(nextError.message);
      } else {
        setError("No se ha podido iniciar sesión.");
      }
      throw nextError;
    } finally {
      setIsSubmitting(false);
    }
  };

  const closeSession = async () => {
    setIsSubmitting(true);
    try {
      const nextSession = await logout({ suppressUnauthorizedEvent: true });
      queryClient.clear();
      queryClient.setQueryData(["auth-session"], nextSession);
    } finally {
      setIsSubmitting(false);
    }
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      session: sessionQuery.data ?? DEFAULT_SESSION,
      isLoading: sessionQuery.isLoading,
      isSubmitting,
      error,
      login,
      logout: closeSession,
      clearError: () => setError(null),
    }),
    [closeSession, error, isSubmitting, sessionQuery.data, sessionQuery.isLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth debe usarse dentro de AuthProvider.");
  }
  return context;
}
