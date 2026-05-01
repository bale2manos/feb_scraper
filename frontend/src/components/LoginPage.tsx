import { FormEvent, useState } from "react";

import { useAuth } from "../auth";

export function LoginPage() {
  const { login, isSubmitting, error, clearError } = useAuth();
  const [password, setPassword] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearError();
    try {
      await login(password);
      setPassword("");
    } catch {
      // El error visible ya se gestiona en el provider.
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="login-copy">
          <span className="eyebrow">FEB Analytics</span>
          <h1>Acceso interno</h1>
          <p>Introduce la contraseña compartida del club para entrar en la app.</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Contraseña del club"
              autoComplete="current-password"
              disabled={isSubmitting}
            />
          </label>
          {error ? <p className="error-text">{error}</p> : null}
          <button type="submit" className="primary-button" disabled={isSubmitting || !password.trim()}>
            {isSubmitting ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}
