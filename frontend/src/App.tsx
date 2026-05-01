import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";

import { AuthProvider, useAuth } from "./auth";
import { LoginPage } from "./components/LoginPage";
import { ReportCenter } from "./components/ReportCenter";
import { DatabasePage } from "./pages/DatabasePage";
import { DependencyPage } from "./pages/DependencyPage";
import { GmPage } from "./pages/GmPage";
import { PhaseReportPage } from "./pages/PhaseReportPage";
import { PotentialPage } from "./pages/PotentialPage";
import { PlayerReportPage } from "./pages/PlayerReportPage";
import { SimilarityPage } from "./pages/SimilarityPage";
import { TeamReportPage } from "./pages/TeamReportPage";
import { TrendsPage } from "./pages/TrendsPage";
import { ReportsProvider } from "./reports";
import { ScopeProvider, useScope } from "./scope";

type AppPage = {
  path: string;
  title: string;
  subtitle: string;
  element: React.ReactNode;
};

function AppRoutes() {
  const { scope, setScope } = useScope();
  const { logout, isSubmitting } = useAuth();

  const pages: AppPage[] = [
    { path: "/gm", title: "GM", subtitle: "Mercado y scouting", element: <GmPage scope={scope} setScope={setScope} /> },
    { path: "/similares", title: "Similares", subtitle: "Buscar reemplazo, montar shortlist y comparar", element: <SimilarityPage scope={scope} setScope={setScope} /> },
    { path: "/potencial", title: "Potencial", subtitle: "Perfiles poco usados con margen de crecimiento", element: <PotentialPage scope={scope} setScope={setScope} /> },
    {
      path: "/dependencia",
      title: "Dependencia",
      subtitle: "Riesgo por equipo y vista general",
      element: <DependencyPage scope={scope} setScope={setScope} />
    },
    { path: "/tendencias", title: "Tendencias", subtitle: "Forma reciente y comparativas", element: <TrendsPage scope={scope} setScope={setScope} /> },
    { path: "/jugador", title: "Jugador", subtitle: "Informe PNG", element: <PlayerReportPage scope={scope} setScope={setScope} /> },
    { path: "/equipo", title: "Equipo", subtitle: "Informe PDF", element: <TeamReportPage scope={scope} setScope={setScope} /> },
    { path: "/fase", title: "Fase", subtitle: "Informe comparativo PDF", element: <PhaseReportPage scope={scope} setScope={setScope} /> },
    { path: "/base-datos", title: "Centro", subtitle: "Control operativo y cobertura", element: <DatabasePage /> }
  ];

  const location = useLocation();
  const resolvedPath = location.pathname === "/mercado" ? "/similares" : location.pathname;
  const activePage = pages.find((page) => page.path === resolvedPath) ?? pages[0];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="topbar-brand">
            <div className="brand-mark">FEB</div>
            <div className="topbar-copy">
              <span className="eyebrow">FEB Analytics</span>
              <strong>{activePage.title}</strong>
              <p>{activePage.subtitle}</p>
            </div>
          </div>

          <nav className="topnav-shell" aria-label="Secciones">
            <div className="topnav">
              {pages.map((page) => (
                <NavLink
                  key={page.path}
                  to={page.path}
                  aria-label={page.title}
                  className={({ isActive }) => (isActive ? "topnav-button is-active" : "topnav-button")}
                >
                  {page.title}
                </NavLink>
              ))}
            </div>
          </nav>

          <div className="topbar-actions">
            <button type="button" className="ghost-button" onClick={() => void logout()} disabled={isSubmitting}>
              {isSubmitting ? "Cerrando..." : "Salir"}
            </button>
          </div>
        </div>
      </header>

      <main className="content-shell">
        <Routes>
          <Route path="/" element={<Navigate to="/gm" replace />} />
          <Route path="/mercado" element={<Navigate to="/similares" replace />} />
          {pages.map((page) => (
            <Route key={page.path} path={page.path} element={page.element} />
          ))}
          <Route path="*" element={<Navigate to="/gm" replace />} />
        </Routes>
      </main>

      <ReportCenter />
    </div>
  );
}

function AppContent() {
  const { session, isLoading } = useAuth();

  if (isLoading) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <div className="login-copy">
            <span className="eyebrow">FEB Analytics</span>
            <h1>Cargando</h1>
            <p>Estamos comprobando tu sesión.</p>
          </div>
        </section>
      </main>
    );
  }

  if (session.authRequired && !session.authenticated) {
    return <LoginPage />;
  }

  return (
    <ScopeProvider>
      <ReportsProvider>
        <AppRoutes />
      </ReportsProvider>
    </ScopeProvider>
  );
}

export default function App() {
  const isTestMode = import.meta.env.MODE === "test";
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 120_000,
            gcTime: isTestMode ? 0 : 10 * 60_000,
            refetchOnWindowFocus: false
          }
        }
      })
  );

  useEffect(
    () => () => {
      queryClient.cancelQueries();
      queryClient.clear();
    },
    [queryClient]
  );

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
