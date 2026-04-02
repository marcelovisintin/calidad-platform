import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { isManagementUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { CompanyLogo } from "../../../components/CompanyLogo";
import { usePageTitle } from "../../../hooks/usePageTitle";

export function LoginPage() {
  usePageTitle("Inicio de sesion");
  const navigate = useNavigate();
  const location = useLocation();
  const { login, status, user } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const requestedDestination = (location.state as { from?: string } | null)?.from;
  const defaultDestination = isManagementUser(user) ? "/dashboard" : "/anomalies/new";
  const redirectTo = requestedDestination || defaultDestination;

  useEffect(() => {
    if (status === "authenticated" && user) {
      if (user.must_change_password) {
        navigate("/change-password", { replace: true, state: { from: redirectTo } });
      } else {
        navigate(redirectTo, { replace: true });
      }
    }
  }, [navigate, redirectTo, status, user]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(identifier, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesion.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-shell">
      <section className="login-card login-card-plant">
        <div className="login-copy">
          <CompanyLogo />
          <h1>Plataforma de calidad</h1>
          <p>Gestion de anomalias, acciones y tareas.</p>
        </div>

        <form className="form-stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Usuario o email</span>
            <input autoComplete="username" onChange={(event) => setIdentifier(event.target.value)} placeholder="admin" required type="text" value={identifier} />
          </label>

          <label className="field">
            <span>Contrasena</span>
            <input autoComplete="current-password" onChange={(event) => setPassword(event.target.value)} placeholder="********" required type="password" value={password} />
          </label>

          {error ? <div className="panel danger">{error}</div> : null}

          <button className="button button-primary button-block" disabled={submitting} type="submit">
            {submitting ? "Ingresando..." : "Ingresar"}
          </button>
        </form>
      </section>
    </div>
  );
}

