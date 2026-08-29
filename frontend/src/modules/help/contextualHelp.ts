import type { HelpTopic } from "./helpContent";
import { HELP_TOPICS_BY_ID } from "./helpContent";

type HelpContext = {
  topic: HelpTopic;
  contextLabel: string;
};

function context(topicId: string, contextLabel: string): HelpContext | null {
  const topic = HELP_TOPICS_BY_ID.get(topicId);
  return topic ? { topic, contextLabel } : null;
}

export function getContextualHelp(
  pathname: string,
  access: { isAdmin: boolean; isManagement: boolean },
): HelpContext | null {
  if (pathname === "/help") {
    return null;
  }

  if (pathname === "/dashboard") {
    return context("orientarse-en-el-sistema", "Panel principal");
  }
  if (pathname === "/anomalies/new" || pathname === "/anomalies/created") {
    return context("registrar-anomalia", "Nueva anomalía");
  }
  if (pathname === "/anomalies/observations" || pathname === "/anomalies/immediate-actions") {
    return access.isManagement
      ? context("gestionar-observacion", "Observaciones")
      : context("consultar-anomalias", "Observaciones");
  }
  if (pathname === "/anomalies/repetition-study") {
    return access.isAdmin
      ? context("clasificar-hallazgo", "Estudio de repetición")
      : context("consultar-anomalias", "Estudio de repetición");
  }
  if (pathname === "/anomalies" || pathname.startsWith("/anomalies/")) {
    return context("consultar-anomalias", pathname === "/anomalies" ? "Seguimiento de anomalías" : "Detalle de anomalía");
  }
  if (pathname === "/treatments/tracking") {
    return context("consultar-tratamientos", "Seguimiento de tratamientos");
  }
  if (pathname === "/treatments") {
    return access.isManagement
      ? context("gestionar-tratamiento", "Tratamientos")
      : context("consultar-tratamientos", "Tratamientos");
  }
  if (pathname === "/learned-lessons") {
    return access.isManagement
      ? context("registrar-leccion", "Lecciones aprendidas")
      : context("consultar-tratamientos", "Lecciones aprendidas");
  }
  if (pathname === "/actions/mine") {
    return context("ejecutar-acciones", "Acciones");
  }
  if (pathname === "/validation") {
    return context("verificar-eficacia", "Validaciones");
  }
  if (pathname === "/notifications/inbox") {
    return context("usar-bandeja", "Bandeja");
  }
  if (pathname === "/indicators" || pathname.startsWith("/indicators/")) {
    return access.isAdmin ? context("consultar-indicadores", "Indicadores") : null;
  }
  if (pathname === "/affected-orders") {
    return access.isAdmin ? context("ordenes-afectadas", "Órdenes afectadas") : null;
  }
  if (pathname === "/management/users/import") {
    return access.isAdmin ? context("importar-usuarios", "Importación de usuarios") : null;
  }
  if (pathname === "/management/users") {
    return access.isAdmin ? context("administrar-usuarios", "Usuarios") : null;
  }
  if (pathname === "/management/user-scopes") {
    return access.isAdmin ? context("configurar-alcances", "Alcances de usuario") : null;
  }
  if (pathname === "/management/catalogs") {
    return access.isAdmin ? context("administrar-catalogos", "Catálogos y maestros") : null;
  }

  return null;
}
