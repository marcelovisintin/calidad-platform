import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { confirmUserImport, previewUserImport } from "../../../api/accounts";
import type { UserImportItem, UserImportMode, UserImportPreview, UserImportResult } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { usePageTitle } from "../../../hooks/usePageTitle";

const importModeOptions: Array<{ value: UserImportMode; label: string }> = [
  { value: "upsert", label: "Crear nuevos y actualizar existentes" },
  { value: "create_only", label: "Crear solo usuarios nuevos" },
  { value: "update_existing", label: "Actualizar usuarios existentes" },
];

function statusLabel(status: UserImportItem["status"]) {
  if (status === "create") return "Nuevo";
  if (status === "update") return "Existente";
  if (status === "skip") return "Omitido";
  return "Error";
}

function csvEscape(value: unknown) {
  const text = String(value ?? "");
  return `"${text.replace(/"/g, '""')}"`;
}

function downloadReport(result: UserImportResult | UserImportPreview) {
  const rows = [
    ["fila", "legajo", "usuario", "nombre", "apellido", "email", "celular", "estado", "errores", "advertencias"],
    ...result.items.map((item) => [
      item.row_number,
      item.legajo,
      item.usuario || "",
      item.nombre || "",
      item.apellido || "",
      item.email,
      item.celular || "",
      statusLabel(item.status),
      item.errors.join(" | "),
      item.warnings.join(" | "),
    ]),
  ];
  const csv = rows.map((row) => row.map(csvEscape).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "reporte_importacion_usuarios.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export function UserBulkImportPage() {
  usePageTitle("Importacion masiva de usuarios");
  const { user } = useAuth();
  const adminUser = isAdminUser(user);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<UserImportMode>("upsert");
  const [preview, setPreview] = useState<UserImportPreview | null>(null);
  const [result, setResult] = useState<UserImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canConfirm = useMemo(() => Boolean(file && preview && preview.summary.errors === 0), [file, preview]);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
    setPreview(null);
    setResult(null);
  };

  const handlePreview = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError("Debe cargar un archivo CSV o Excel.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setPreview(await previewUserImport(file, mode));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo analizar el archivo.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const nextResult = await confirmUserImport(file, mode);
      setResult(nextResult);
      setPreview(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo confirmar la importacion.");
    } finally {
      setLoading(false);
    }
  };

  if (!adminUser) {
    return (
      <section className="page-shell">
        <PageHeader title="Importacion masiva" actionLabel="Volver a usuarios" actionTo="/management/users" />
        <section className="panel warning">
          <h2>Acceso restringido</h2>
          <p>Necesitas perfil administrador para importar usuarios.</p>
          <Link className="button button-secondary" to="/management/users">
            Volver a usuarios
          </Link>
        </section>
      </section>
    );
  }

  const activeReport = result || preview;

  return (
    <section className="page-shell">
      <PageHeader title="Importacion masiva de usuarios" actionLabel="Volver a usuarios" actionTo="/management/users" compact />

      {error ? <div className="panel danger">{error}</div> : null}

      <section className="panel">
        <form className="form-grid" onSubmit={handlePreview}>
          <label className="field">
            <span>Archivo CSV o Excel</span>
            <input accept=".csv,.xlsx" onChange={handleFileChange} required type="file" />
            <small>Columnas: legajo, nombre, apellido, e-mail, usuario, celular. Legajo y celular son opcionales.</small>
          </label>
          <label className="field">
            <span>Comportamiento</span>
            <select onChange={(event) => setMode(event.target.value as UserImportMode)} value={mode}>
              {importModeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div className="field user-import-actions">
            <button className="button button-primary" disabled={loading || !file} type="submit">
              {loading ? "Analizando..." : "Analizar archivo"}
            </button>
            <button className="button button-secondary" disabled={loading || !canConfirm} onClick={handleConfirm} type="button">
              Confirmar importacion
            </button>
          </div>
        </form>
      </section>

      <DataState loading={loading} error={null}>
        {activeReport ? (
          <section className="panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">{result ? "Reporte final" : "Vista previa"}</p>
                <h2>{result ? "Importacion procesada" : "Resultado del analisis"}</h2>
              </div>
              <button className="button button-secondary" onClick={() => downloadReport(activeReport)} type="button">
                Descargar CSV
              </button>
            </div>

            <div className="summary-grid user-import-summary">
              {result ? (
                <>
                  <div><strong>{result.summary.created}</strong><span>Creados</span></div>
                  <div><strong>{result.summary.updated}</strong><span>Actualizados</span></div>
                  <div><strong>{result.summary.skipped}</strong><span>Omitidos</span></div>
                  <div><strong>{result.summary.errors}</strong><span>Errores</span></div>
                  <div><strong>{result.summary.warnings}</strong><span>Advertencias</span></div>
                </>
              ) : (
                <>
                  <div><strong>{preview?.summary.new_users}</strong><span>Nuevos</span></div>
                  <div><strong>{preview?.summary.existing_users}</strong><span>Existentes</span></div>
                  <div><strong>{preview?.summary.errors}</strong><span>Con errores</span></div>
                  <div><strong>{preview?.summary.duplicate_emails}</strong><span>Emails repetidos</span></div>
                  <div><strong>{preview?.summary.duplicate_legajos}</strong><span>Legajos repetidos</span></div>
                  <div><strong>{preview?.summary.duplicate_usernames}</strong><span>Usuarios repetidos</span></div>
                </>
              )}
            </div>

            <div className="table-scroll user-import-table">
              <table>
                <thead>
                  <tr>
                    <th>Fila</th>
                    <th>Legajo</th>
                    <th>Usuario</th>
                    <th>Nombre</th>
                    <th>Apellido</th>
                    <th>Email</th>
                    <th>Celular</th>
                    <th>Estado</th>
                    <th>Observaciones</th>
                  </tr>
                </thead>
                <tbody>
                  {activeReport.items.map((item) => (
                    <tr key={`${item.row_number}-${item.email}`}>
                      <td>{item.row_number}</td>
                      <td>{item.legajo || "-"}</td>
                      <td>{item.usuario || "-"}</td>
                      <td>{item.nombre || "-"}</td>
                      <td>{item.apellido || "-"}</td>
                      <td>{item.email}</td>
                      <td>{item.celular || "-"}</td>
                      <td><span className={`status-pill status-${item.status}`}>{statusLabel(item.status)}</span></td>
                      <td>
                        {[...item.errors, ...item.warnings].length
                          ? [...item.errors, ...item.warnings].join(" | ")
                          : "Sin observaciones"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}
      </DataState>
    </section>
  );
}
