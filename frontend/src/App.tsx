import { useLocalStorageState } from "./hooks";
import { DependencyPage } from "./pages/DependencyPage";
import { GmPage } from "./pages/GmPage";
import { TrendsPage } from "./pages/TrendsPage";

type PageKey = "gm" | "dependency" | "trends";

export default function App() {
  const [page, setPage] = useLocalStorageState<PageKey>("react-active-page", "gm");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>FEB Analytics</h1>
        <p className="sidebar-copy">Migración incremental desde Streamlit a una interfaz más ágil y más fácil de escalar.</p>
        <nav className="nav-stack">
          <button type="button" className={page === "gm" ? "nav-button is-active" : "nav-button"} onClick={() => setPage("gm")}>
            GM
          </button>
          <button type="button" className={page === "dependency" ? "nav-button is-active" : "nav-button"} onClick={() => setPage("dependency")}>
            Dependencia
          </button>
          <button type="button" className={page === "trends" ? "nav-button is-active" : "nav-button"} onClick={() => setPage("trends")}>
            Tendencias
          </button>
        </nav>
      </aside>
      <main className="content-shell">
        {page === "gm" ? <GmPage /> : null}
        {page === "dependency" ? <DependencyPage /> : null}
        {page === "trends" ? <TrendsPage /> : null}
      </main>
    </div>
  );
}
