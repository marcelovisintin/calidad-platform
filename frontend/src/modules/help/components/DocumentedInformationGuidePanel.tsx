import { DOCUMENTED_INFORMATION_GUIDE } from "../documentedInformationGuide";

export function DocumentedInformationGuidePanel() {
  return (
    <aside className="help-documented-guide" id="documented-information-guide">
      <header>
        <p className="eyebrow">Referencia de gestión</p>
        <h2>{DOCUMENTED_INFORMATION_GUIDE.title}</h2>
      </header>
      {DOCUMENTED_INFORMATION_GUIDE.introduction.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}

      <section>
        <h3>La información documentada sirve para</h3>
        <ul>{DOCUMENTED_INFORMATION_GUIDE.purposes.map((item) => <li key={item}>{item}</li>)}</ul>
        <p>{DOCUMENTED_INFORMATION_GUIDE.media}</p>
      </section>

      <section>
        <h3>La organización debe</h3>
        <ul>{DOCUMENTED_INFORMATION_GUIDE.organizationResponsibilities.map((item) => <li key={item}>{item}</li>)}</ul>
        <p>{DOCUMENTED_INFORMATION_GUIDE.proportionality}</p>
      </section>

      <div className="help-document-lists">
        <section>
          <h3>Documentos que pueden aportar valor</h3>
          <ul>{DOCUMENTED_INFORMATION_GUIDE.valuableDocuments.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
        <section>
          <h3>Registros conservados como evidencia</h3>
          <ul>{DOCUMENTED_INFORMATION_GUIDE.evidenceRecords.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      </div>

      <section>
        <h3>Para las no conformidades deben conservarse</h3>
        <ul>{DOCUMENTED_INFORMATION_GUIDE.nonConformityRecords.map((item) => <li key={item}>{item}</li>)}</ul>
      </section>

      <p className="help-document-principle">{DOCUMENTED_INFORMATION_GUIDE.processFirst}</p>
      <p>{DOCUMENTED_INFORMATION_GUIDE.auditEvidence}</p>

      <section className="help-system-recommendations">
        <h3>Lo más importante para el Sistema de Gestión de Calidad</h3>
        <p>{DOCUMENTED_INFORMATION_GUIDE.systemFocus}</p>
        <div className="help-recommendation-warning">
          <strong>Criterios recomendados:</strong> esta tabla expresa requisitos y objetivos de diseño. No confirma por sí sola que cada punto esté implementado en el código actual.
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Requisito del sistema</th><th>Aplicación concreta</th></tr></thead>
            <tbody>
              {DOCUMENTED_INFORMATION_GUIDE.systemRecommendations.map((item) => (
                <tr key={item.requirement}><th scope="row">{item.requirement}</th><td>{item.application}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="help-iso-links">
        <a href="https://www.iso.org/files/live/sites/isoorg/files/archive/pdf/en/documented_information.pdf" rel="noreferrer" target="_blank">Consultar la guía oficial de ISO</a>
      </div>
    </aside>
  );
}
