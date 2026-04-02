import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../app/providers/AuthProvider";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <div className="page-shell"><div className="skeleton-card">Cargando sesion...</div></div>;
  }

  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (user?.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace state={{ from: location.pathname }} />;
  }

  if (!user?.must_change_password && location.pathname === "/change-password") {
    const requested = (location.state as { from?: string } | null)?.from;
    const destination = requested && requested !== "/change-password" ? requested : "/dashboard";
    return <Navigate to={destination} replace />;
  }

  return <>{children}</>;
}
