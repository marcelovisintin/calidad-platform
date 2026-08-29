import { Navigate } from "react-router-dom";
import { getDefaultLandingPath, isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { PageHeader } from "../../../components/PageHeader";
import { usePageTitle } from "../../../hooks/usePageTitle";
import { IndicatorsCatalog } from "../components/IndicatorsCatalog";


export function IndicatorsPage() {
  usePageTitle("Indicadores");
  const { user } = useAuth();

  if (!isAdminUser(user)) {
    return <Navigate replace to={getDefaultLandingPath(user)} />;
  }

  return (
    <section className="page-shell page-shell-management">
      <PageHeader
        title="Indicadores"
        description="Dashboards de gestion, evolucion, cumplimiento y eficacia del Sistema de Gestion de Calidad."
        actionLabel="Volver al panel"
        actionTo="/dashboard?view=indicators"
      />
      <section className="panel">
        <div className="section-head compact">
          <div>
            <p className="eyebrow">Analisis integral</p>
            <h2>Selecciona un indicador</h2>
          </div>
        </div>
        <IndicatorsCatalog />
      </section>
    </section>
  );
}
