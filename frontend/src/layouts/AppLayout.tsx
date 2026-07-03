import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { createAuthenticatedObjectUrl } from "../api/files";
import { useAuth } from "../app/providers/AuthProvider";
import { CompanyLogo } from "../components/CompanyLogo";

const mainNav = [
  { to: "/dashboard", label: "Inicio", mobileLabel: "Inicio" },
  { to: "/anomalies/new", label: "Nueva", mobileLabel: "Nueva" },
  { to: "/anomalies", label: "Seguimiento de anomalias", mobileLabel: "Anomalias" },
  { to: "/treatments/tracking", label: "Seguimiento de tratamientos", mobileLabel: "Seg. trat." },
  { to: "/learned-lessons", label: "Lecciones aprendidas", mobileLabel: "Lecciones" },
  { to: "/anomalies/observations", label: "Observacion", mobileLabel: "Observacion" },
  { to: "/treatments", label: "Tratamientos", mobileLabel: "Tratamientos" },
  { to: "/actions/mine", label: "Acciones", mobileLabel: "Acciones" },
  { to: "/validation", label: "Validacion", mobileLabel: "Validacion" },
  { to: "/tasks", label: "Pendientes", mobileLabel: "Pendientes" },
  { to: "/notifications/inbox", label: "Bandeja", mobileLabel: "Bandeja" },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const currentSection =
    mainNav.find((item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`))?.label ||
    (location.pathname.startsWith("/management/users") ? "Usuarios" : location.pathname.startsWith("/management/catalogs") ? "Catalogos" : "Plataforma");
  const userTag = user?.username || user?.email?.split("@")[0] || "usuario";
  const [photoSrc, setPhotoSrc] = useState("");
  const canGoBack = (window.history.state?.idx ?? 0) > 0;

  useEffect(() => {
    let objectUrl = "";
    let cancelled = false;

    setPhotoSrc("");
    if (!user?.photo_url) {
      return;
    }

    void createAuthenticatedObjectUrl(user.photo_url).then((url) => {
      if (cancelled) {
        if (url) {
          URL.revokeObjectURL(url);
        }
        return;
      }
      objectUrl = url;
      setPhotoSrc(url);
    });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [user?.photo_url]);

  const handleGoBack = () => {
    if (canGoBack) {
      navigate(-1);
      return;
    }
    navigate("/dashboard", { replace: true });
  };

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-block">
          <CompanyLogo compact inverted />
          <strong className="brand-title">Plataforma de calidad</strong>
          <p className="brand-copy">Registro, gestion y seguimiento de anomalias en planta.</p>
        </div>

        <nav className="side-nav">
          {mainNav.map((item) => (
            <NavLink
              key={item.to}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              to={item.to}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-panel">
            <strong>{user?.full_name || userTag}</strong>
            <span>{user?.role_codes.join(" / ") || "Sin rol"}</span>
          </div>
          <button className="button button-secondary" onClick={() => void logout()} type="button">
            Cerrar sesion
          </button>
        </div>
      </aside>

      <div className="app-main-frame">
        <header className="topbar topbar-compact">
          <div className="topbar-left">
            <button className="button button-secondary topbar-back" onClick={handleGoBack} type="button">
              Volver
            </button>
            <strong className="topbar-title">{currentSection}</strong>
          </div>
          <div className="topbar-user" title={user?.full_name || userTag}>
            {photoSrc ? (
              <img alt="" className="topbar-user-photo" src={photoSrc} />
            ) : (
              <span className="topbar-user-initial">{userTag.slice(0, 1).toUpperCase()}</span>
            )}
            <span>{user?.full_name || userTag}</span>
          </div>
        </header>

        <main className="app-content">
          <Outlet />
        </main>

        <nav className="bottom-nav">
          {mainNav.map((item) => (
            <NavLink
              key={item.to}
              className={({ isActive }) => `bottom-link${isActive ? " active" : ""}`}
              to={item.to}
            >
              {item.mobileLabel}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}





