import { FormEvent, useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { fetchEmailTemplates, resetEmailTemplate, updateEmailTemplate } from "../../../api/emailTemplates";
import type { EmailTemplateDefinition } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

function renderPreview(template: string, item: EmailTemplateDefinition) {
  return item.allowed_fields.reduce(
    (result, field) => result.split(`{${field.key}}`).join(field.example),
    template,
  ).split("{{").join("{").split("}}").join("}");
}

export function EmailTemplateManagementPage() {
  usePageTitle("Edición correos");
  const { user } = useAuth();
  const adminUser = isAdminUser(user);
  const { data, loading, error, reload } = useAsyncTask(
    () => (adminUser ? fetchEmailTemplates() : Promise.resolve([])),
    [adminUser],
  );
  const [search, setSearch] = useState("");
  const [selectedCode, setSelectedCode] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [activeEditor, setActiveEditor] = useState<"subject" | "body">("body");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const filteredItems = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("es");
    if (!term) return data ?? [];
    return (data ?? []).filter((item) =>
      [item.case_number, item.name, item.stage, item.recipient, item.description]
        .join(" ")
        .toLocaleLowerCase("es")
        .includes(term),
    );
  }, [data, search]);

  const selected = useMemo(
    () => data?.find((item) => item.code === selectedCode) ?? data?.[0] ?? null,
    [data, selectedCode],
  );

  useEffect(() => {
    if (!selected) return;
    setSelectedCode(selected.code);
    setSubject(selected.subject_template);
    setBody(selected.body_template);
  }, [selected]);

  if (!adminUser) {
    return <Navigate replace to="/" />;
  }

  const handleSelect = (item: EmailTemplateDefinition) => {
    setSelectedCode(item.code);
    setFeedback(null);
    setSubmitError(null);
  };

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    if (!window.confirm("¿Guardar este texto para los próximos correos de este caso?")) return;
    setSaving(true);
    setFeedback(null);
    setSubmitError(null);
    try {
      const updated = await updateEmailTemplate(selected.code, {
        subject_template: subject,
        body_template: body,
        row_version: selected.row_version,
      });
      setSubject(updated.subject_template);
      setBody(updated.body_template);
      setFeedback("Texto guardado. Se aplicará únicamente a los próximos correos.");
      await reload();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "No se pudo guardar el correo.");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!selected?.is_customized) return;
    if (!window.confirm("¿Restaurar el asunto y cuerpo originales de este caso?")) return;
    setSaving(true);
    setFeedback(null);
    setSubmitError(null);
    try {
      const restored = await resetEmailTemplate(selected.code);
      setSubject(restored.subject_template);
      setBody(restored.body_template);
      setFeedback("Se restauró el texto original.");
      await reload();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "No se pudo restaurar el correo.");
    } finally {
      setSaving(false);
    }
  };

  const insertField = (key: string) => {
    const append = (current: string) => `${current}${current.endsWith("\n") || !current ? "" : " "}{${key}}`;
    if (activeEditor === "subject") {
      setSubject(append);
    } else {
      setBody(append);
    }
  };

  return (
    <section className="page-stack">
      <PageHeader
        actionLabel="Volver a configuración"
        actionTo="/dashboard?view=admin"
        description="Administra asunto y cuerpo de cada correo saliente sin modificar sus destinatarios ni reglas de envío."
        title="Edición correos"
      />

      <div className="panel muted email-template-note">
        <strong>Alcance seguro</strong>
        <p>Los cambios afectan solo correos futuros. La etapa, el destinatario y la notificación interna permanecen definidos por el sistema.</p>
      </div>

      <DataState loading={loading} error={error} empty={!data?.length} onRetry={() => void reload()}>
        <div className="email-template-workspace">
          <aside className="panel email-template-directory">
            <label className="field">
              <span>Buscar caso</span>
              <input
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Caso, etapa o destinatario"
                type="search"
                value={search}
              />
            </label>
            <p className="muted-copy">{filteredItems.length} variantes de correo</p>
            <div className="email-template-list">
              {filteredItems.map((item) => (
                <button
                  className={`email-template-card${selected?.code === item.code ? " active" : ""}`}
                  key={item.code}
                  onClick={() => handleSelect(item)}
                  type="button"
                >
                  <span>Caso {item.case_number}</span>
                  <strong>{item.name}</strong>
                  <small>{item.stage}</small>
                  <em>{item.is_customized ? "Personalizado" : "Texto original"}</em>
                </button>
              ))}
              {!filteredItems.length ? <p className="muted-copy">No hay casos que coincidan con la búsqueda.</p> : null}
            </div>
          </aside>

          <main className="panel email-template-editor">
            {selected ? (
              <form className="form-section" onSubmit={handleSave}>
                <div className="section-head compact">
                  <div>
                    <p className="eyebrow">Caso {selected.case_number}</p>
                    <h2>{selected.name}</h2>
                  </div>
                  <span className={`email-template-state${selected.is_customized ? " customized" : ""}`}>
                    {selected.is_customized ? "Personalizado" : "Original"}
                  </span>
                </div>

                <dl className="key-grid email-template-metadata">
                  <div><dt>Etapa</dt><dd>{selected.stage}</dd></div>
                  <div><dt>Destinatario</dt><dd>{selected.recipient}</dd></div>
                  <div><dt>Cuándo se genera</dt><dd>{selected.description}</dd></div>
                  <div><dt>Condiciones</dt><dd>{selected.conditions}</dd></div>
                </dl>

                <label className="field">
                  <span>Asunto</span>
                  <input
                    maxLength={255}
                    onChange={(event) => setSubject(event.target.value)}
                    onFocus={() => setActiveEditor("subject")}
                    required
                    value={subject}
                  />
                </label>
                <label className="field">
                  <span>Cuerpo</span>
                  <textarea
                    onChange={(event) => setBody(event.target.value)}
                    onFocus={() => setActiveEditor("body")}
                    required
                    rows={11}
                    value={body}
                  />
                </label>

                <div>
                  <strong>Campos disponibles</strong>
                  <p className="muted-copy">
                    Haz clic para insertarlo al final de {activeEditor === "subject" ? "asunto" : "cuerpo"}. No cambies el texto dentro de las llaves.
                  </p>
                  <div className="email-template-fields">
                    {selected.allowed_fields.map((field) => (
                      <button key={field.key} onClick={() => insertField(field.key)} title={field.label} type="button">
                        {`{${field.key}}`}
                      </button>
                    ))}
                  </div>
                </div>

                <section className="email-template-preview">
                  <p className="eyebrow">Vista previa con datos de ejemplo</p>
                  <strong>{renderPreview(subject, selected)}</strong>
                  <p>{renderPreview(body, selected)}</p>
                </section>

                {submitError ? <div className="panel danger">{submitError}</div> : null}
                {feedback ? <div className="panel success">{feedback}</div> : null}
                <div className="form-actions">
                  <button className="button button-primary" disabled={saving} type="submit">
                    {saving ? "Guardando..." : "Guardar cambios"}
                  </button>
                  <button
                    className="button button-secondary"
                    disabled={saving || !selected.is_customized}
                    onClick={() => void handleReset()}
                    type="button"
                  >
                    Restaurar original
                  </button>
                  {selected.updated_at ? (
                    <small>
                      Última edición: {formatDateTime(selected.updated_at)}{selected.updated_by ? ` por ${selected.updated_by}` : ""}
                    </small>
                  ) : null}
                </div>
              </form>
            ) : (
              <p className="muted-copy">Selecciona un caso para editarlo.</p>
            )}
          </main>
        </div>
      </DataState>
    </section>
  );
}
