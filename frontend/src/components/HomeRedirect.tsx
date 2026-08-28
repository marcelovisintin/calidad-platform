import { Navigate } from "react-router-dom";
import { getDefaultLandingPath } from "../app/access";
import { useAuth } from "../app/providers/AuthProvider";

export function HomeRedirect() {
  const { status, user } = useAuth();

  if (status === "loading") {
    return <div className="page-shell"><div className="skeleton-card">Preparando espacio de trabajo...</div></div>;
  }

  if (user?.must_change_password) {
    return <Navigate replace to="/change-password" />;
  }

  return <Navigate replace to={getDefaultLandingPath(user)} />;
}
