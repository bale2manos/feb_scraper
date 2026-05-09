import { FormEvent, useState } from "react";

import { getGoogleOidcLoginUrl } from "../api";
import { useAuth } from "../auth";

export function LoginPage() {
  const { session, login, isSubmitting, error, clearError } = useAuth();
  const [password, setPassword] = useState("");
  const passwordLoginEnabled = session.passwordLoginEnabled ?? true;
  const oidcLoginEnabled = Boolean(session.oidcLoginEnabled);

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

  function handleGoogleLogin() {
    clearError();
    window.location.assign(getGoogleOidcLoginUrl());
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="login-copy">
          <span className="eyebrow">FEB Analytics</span>
          <h1>Acceso interno</h1>
          <p>Accede con Google OpenID Connect o con la contrasena interna si esta habilitada.</p>
        </div>

        <div className="login-form">
          {oidcLoginEnabled ? (
            <button type="button" className="primary-button google-login-button" onClick={handleGoogleLogin} disabled={isSubmitting}>
              Entrar con Google
            </button>
          ) : null}

          {oidcLoginEnabled && passwordLoginEnabled ? <div className="login-separator">o</div> : null}

          {passwordLoginEnabled ? (
            <form className="login-password-form" onSubmit={handleSubmit}>
              <label>
                Contrasena
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Contrasena del club"
                  autoComplete="current-password"
                  disabled={isSubmitting}
                />
              </label>
              <button type="submit" className="secondary-button" disabled={isSubmitting || !password.trim()}>
                {isSubmitting ? "Entrando..." : "Entrar con contrasena"}
              </button>
            </form>
          ) : null}

          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </section>
    </main>
  );
}
