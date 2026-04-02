import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../../../api/http";
import { useAuth } from "../../../app/providers/AuthProvider";
import { CompanyLogo } from "../../../components/CompanyLogo";
import { usePageTitle } from "../../../hooks/usePageTitle";

function flattenValidationValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => flattenValidationValue(item)).filter(Boolean).join(", ");
  }
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value === "object" && "detail" in value) {
    return String((value as { detail?: unknown }).detail ?? "");
  }
  return "";
}

function resolveChangePasswordError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : "No se pudo cambiar la contrasena.";
  }

  const payload = error.payload;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return error.message || "No se pudo cambiar la contrasena.";
  }

  const values = payload as Record<string, unknown>;
  const preferredFields = ["current_password", "new_password", "confirm_password", "non_field_errors", "detail"];
  for (const field of preferredFields) {
    if (field in values) {
      const message = flattenValidationValue(values[field]);
      if (message) {
        return message;
      }
    }
  }

  const fallback = Object.values(values)
    .map((item) => flattenValidationValue(item))
    .find(Boolean);

  return fallback || error.message || "No se pudo cambiar la contrasena.";
}

export function ChangePasswordPage() {
  usePageTitle("Cambio de contrasena");
  const navigate = useNavigate();
  const location = useLocation();
  const { user, status, changePassword } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const requestedDestination = (location.state as { from?: string } | null)?.from;

  useEffect(() => {
    if (status === "authenticated" && user && !user.must_change_password) {
      navigate(requestedDestination && requestedDestination !== "/change-password" ? requestedDestination : "/dashboard", {
        replace: true,
      });
    }
  }, [navigate, requestedDestination, status, user]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      navigate(requestedDestination && requestedDestination !== "/change-password" ? requestedDestination : "/dashboard", {
        replace: true,
      });
    } catch (err) {
      setError(resolveChangePasswordError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-shell">
      <section className="login-card login-card-plant">
        <div className="login-copy">
          <CompanyLogo />
          <h1>Cambio obligatorio de contrasena</h1>
          <p>Por seguridad, antes de continuar debes definir una contrasena fuerte.</p>
          {user ? (
            <p className="muted-copy">
              Usuario: <strong>{user.username}</strong>
              {user.email ? ` · ${user.email}` : ""}
            </p>
          ) : null}
        </div>

        <div className="panel muted">
          <strong>Requisitos:</strong>
          <ul>
            <li>Minimo 10 caracteres</li>
            <li>Al menos una mayuscula, una minuscula, un numero y un simbolo</li>
            <li>No debe incluir tu usuario o partes de tu email</li>
          </ul>
        </div>

        <form className="form-stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Contrasena actual</span>
            <input
              autoComplete="current-password"
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
              type="password"
              value={currentPassword}
            />
          </label>

          <label className="field">
            <span>Nueva contrasena</span>
            <input
              autoComplete="new-password"
              onChange={(event) => setNewPassword(event.target.value)}
              required
              type="password"
              value={newPassword}
            />
          </label>

          <label className="field">
            <span>Confirmar nueva contrasena</span>
            <input
              autoComplete="new-password"
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              type="password"
              value={confirmPassword}
            />
          </label>

          {error ? <div className="panel danger">{error}</div> : null}

          <button className="button button-primary button-block" disabled={submitting} type="submit">
            {submitting ? "Guardando..." : "Guardar contrasena"}
          </button>
        </form>
      </section>
    </div>
  );
}
