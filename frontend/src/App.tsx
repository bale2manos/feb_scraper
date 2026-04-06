import { useLocalStorageState } from "./hooks";
import { DependencyPage } from "./pages/DependencyPage";
import { GmPage } from "./pages/GmPage";
import { TrendsPage } from "./pages/TrendsPage";

type PageKey = "gm" | "dependency" | "trends";

const APP_PAGES: { key: PageKey; title: string; tagline: string; badge: string }[] = [
  {
    key: "gm",
    title: "GM",
    tagline: "Mercado, lectura rapida y filtros de scouting con una interfaz mucho mas limpia.",
    badge: "Base"
  },
  {
    key: "dependency",
    title: "Dependencia",
    tagline: "Riesgo estructural, jugadores criticos y diagnostico visual del equipo.",
    badge: "Riesgo"
  },
  {
    key: "trends",
    title: "Tendencias",
    tagline: "Evolucion reciente de jugadores y equipos con mejor lectura comparativa.",
    badge: "Forma"
  }
];

export default function App() {
  const [page, setPage] = useLocalStorageState<PageKey>("react-active-page", "gm");
  const activePage = APP_PAGES.find((item) => item.key === page) ?? APP_PAGES[0];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="eyebrow eyebrow-dark">Nueva capa web</span>
          <h1>FEB Analytics</h1>
          <p className="sidebar-copy">
            Mismas ideas de producto, pero implementadas con una navegacion mas comoda, mas rapidez percibida y mejor lectura en escritorio y movil.
          </p>
        </div>

        <nav className="nav-stack">
          {APP_PAGES.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-label={item.title}
              className={page === item.key ? "nav-button is-active" : "nav-button"}
              onClick={() => setPage(item.key)}
            >
              <span className="nav-button-badge">{item.badge}</span>
              <strong>{item.title}</strong>
              <span>{item.tagline}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-note">
          <span className="scope-badge">Responsive</span>
          <span className="scope-badge">Mas visual</span>
          <span className="scope-badge">Mas util en reunion</span>
        </div>
      </aside>

      <main className="content-shell">
        <header className="content-hero panel">
          <div>
            <span className="eyebrow">Workspace activo</span>
            <h2>{activePage.title}</h2>
            <p className="panel-copy">{activePage.tagline}</p>
          </div>
          <div className="hero-stats">
            <div className="hero-stat">
              <span>Navegacion</span>
              <strong>Separada por vista</strong>
            </div>
            <div className="hero-stat">
              <span>Lectura</span>
              <strong>Mas limpia y rapida</strong>
            </div>
            <div className="hero-stat">
              <span>Objetivo</span>
              <strong>Mas comoda para uso real</strong>
            </div>
          </div>
        </header>

        {page === "gm" ? <GmPage /> : null}
        {page === "dependency" ? <DependencyPage /> : null}
        {page === "trends" ? <TrendsPage /> : null}
      </main>
    </div>
  );
}
