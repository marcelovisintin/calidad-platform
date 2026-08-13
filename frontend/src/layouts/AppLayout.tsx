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
  const [menuOpen, setMenuOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const currentSection =
    mainNav.find((item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`))?.label ||
    (location.pathname.startsWith("/management/users") ? "Usuarios" : location.pathname.startsWith("/management/catalogs") ? "Catalogos" : "Plataforma");
  const userTag = user?.username || user?.email?.split("@")[0] || "usuario";
  const [photoSrc, setPhotoSrc] = useState("");
  const canGoBack = (window.history.state?.idx ?? 0) > 0;

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

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

  const handleLogout = async () => {
    if (loggingOut) {
      return;
    }
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
      navigate("/login", { replace: true });
    }
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
            <span>{user?.access_level?.replaceAll("_", " ") || "Sin nivel"}</span>
          </div>
          <button className="button button-secondary" onClick={() => void handleLogout()} type="button">
            Cerrar sesión
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
          <div className="topbar-actions">
            <div className="topbar-user" title={user?.full_name || userTag}>
              {photoSrc ? (
                <img alt="" className="topbar-user-photo" src={photoSrc} />
              ) : (
                <span className="topbar-user-initial">{userTag.slice(0, 1).toUpperCase()}</span>
              )}
              <span>{user?.full_name || userTag}</span>
            </div>
            <button
              className="button button-secondary topbar-logout"
              disabled={loggingOut}
              onClick={() => void handleLogout()}
              type="button"
            >
              {loggingOut ? "Saliendo..." : "Cerrar sesión"}
            </button>
            <button
              aria-expanded={menuOpen}
              aria-controls="responsive-navigation"
              className="button button-primary topbar-menu"
              onClick={() => setMenuOpen(true)}
              type="button"
            >
              Menú
            </button>
          </div>
        </header>

        <main className="app-content">
          <Outlet />
        </main>

      </div>

      <div className={`mobile-nav-layer${menuOpen ? " open" : ""}`} aria-hidden={!menuOpen}>
        <button
          aria-label="Cerrar menú"
          className="mobile-nav-backdrop"
          onClick={() => setMenuOpen(false)}
          tabIndex={menuOpen ? 0 : -1}
          type="button"
        />
        <aside
          aria-label="Navegación principal"
          className="mobile-nav-drawer"
          id="responsive-navigation"
        >
          <div className="mobile-nav-head">
            <div>
              <CompanyLogo compact inverted />
              <strong>Plataforma de calidad</strong>
            </div>
            <button
              aria-label="Cerrar menú"
              className="button button-secondary mobile-nav-close"
              onClick={() => setMenuOpen(false)}
              type="button"
            >
              Cerrar
            </button>
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
          <div className="mobile-nav-footer">
            <div className="user-panel">
              <strong>{user?.full_name || userTag}</strong>
              <span>{user?.access_level?.replaceAll("_", " ") || "Sin nivel"}</span>
            </div>
            <button
              className="button button-secondary button-block"
              disabled={loggingOut}
              onClick={() => void handleLogout()}
              type="button"
            >
              {loggingOut ? "Saliendo..." : "Cerrar sesión"}
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}





