import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { createCatalogItem, deleteCatalogItem, fetchCatalogItems, updateCatalogItem } from "../../../api/catalog";
import type { CatalogEntity, CatalogManagementItem } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

type FormState = {
  code: string;
  name: string;
  display_order: string;
  is_active: boolean;
  parent_id: string;
};

type EntityMeta = {
  key: CatalogEntity;
  title: string;
  description: string;
  parentEntity?: CatalogEntity;
  parentLabel?: string;
  parentKey?: "site_id" | "area_id";
};

const ENTITY_META: EntityMeta[] = [
  {
    key: "sites",
    title: "Areas",
    description: "Areas principales de la empresa donde opera el sistema.",
  },
  {
    key: "areas",
    title: "Procesos",
    description: "Procesos o subsectores de trabajo disponibles para el registro.",
    parentEntity: "sites",
    parentLabel: "Area",
    parentKey: "site_id",
  },
  {
    key: "lines",
    title: "Lineas",
    description: "Lineas o puestos productivos utilizados en el proceso.",
    parentEntity: "areas",
    parentLabel: "Proceso",
    parentKey: "area_id",
  },
  {
    key: "anomaly-types",
    title: "Tipos de anomalia",
    description: "Catalogo de defectos, desvios o eventos de calidad.",
  },
  {
    key: "anomaly-origins",
    title: "Origenes",
    description: "Origen o fuente primaria asociada a la anomalia.",
  },
  {
    key: "severities",
    title: "Criterios de clasificacion",
    description: "Criterios usados para clasificar cada anomalia.",
  },
  {
    key: "priorities",
    title: "Prioridades",
    description: "Prioridades operativas y de tratamiento.",
  },
  {
    key: "action-types",
    title: "Tipos de accion",
    description: "Contencion, correctiva, preventiva o mejora.",
  },
];

const EMPTY_FORM: FormState = {
  code: "",
  name: "",
  display_order: "0",
  is_active: true,
  parent_id: "",
};

function resolveEntity(raw: string | null): CatalogEntity {
  const valid = new Set(ENTITY_META.map((item) => item.key));
  if (raw && valid.has(raw as CatalogEntity)) {
    return raw as CatalogEntity;
  }
  return "sites";
}

function itemParentLabel(item: CatalogManagementItem) {
  if (item.site) {
    return `${item.site.code} - ${item.site.name}`;
  }
  if (item.area) {
    return `${item.area.code} - ${item.area.name}`;
  }
  return "";
}

export function CatalogManagementPage() {
  usePageTitle("Catalogos");
  const { user } = useAuth();
  const adminUser = isAdminUser(user);

  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [busyDeleteId, setBusyDeleteId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const entity = resolveEntity(searchParams.get("entity"));
  const meta = useMemo(() => ENTITY_META.find((item) => item.key === entity) ?? ENTITY_META[0], [entity]);

  const { data, loading, error, reload } = useAsyncTask(async () => {
    const [items, parents] = await Promise.all([
      fetchCatalogItems(entity, {
        active: includeInactive ? undefined : true,
        q: search,
      }),
      meta.parentEntity
        ? fetchCatalogItems(meta.parentEntity, {
            active: undefined,
          })
        : Promise.resolve({ count: 0, next: null, previous: null, results: [] as CatalogManagementItem[] }),
    ]);

    return {
      total: items.count,
      items: items.results,
      parents: parents.results,
    };
  }, [entity, includeInactive, meta.parentEntity, search]);

  const parentOptions = data?.parents ?? [];
  const items = data?.items ?? [];

  const changeEntity = (next: CatalogEntity) => {
    setSearchParams({ entity: next });
    setEditingId(null);
    setForm(EMPTY_FORM);
    setSubmitError(null);
    setFeedback(null);
  };

  const resetForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setSubmitError(null);
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = event.target;
    if (type === "checkbox") {
      const target = event.target as HTMLInputElement;
      setForm((current) => ({ ...current, [name]: target.checked }));
      return;
    }

    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleEdit = (item: CatalogManagementItem) => {
    setEditingId(item.id);
    setSubmitError(null);
    setFeedback(null);

    const parentId = meta.parentKey === "site_id" ? item.site?.id || "" : meta.parentKey === "area_id" ? item.area?.id || "" : "";

    setForm({
      code: item.code,
      name: item.name,
      display_order: String(item.display_order ?? 0),
      is_active: item.is_active,
      parent_id: parentId,
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setFeedback(null);

    try {
      const payload: Record<string, unknown> = {
        code: form.code.trim(),
        name: form.name.trim(),
        display_order: Number(form.display_order || 0),
        is_active: form.is_active,
      };

      if (meta.parentKey) {
        if (!form.parent_id) {
          throw new Error(`Selecciona ${meta.parentLabel?.toLowerCase() ?? "el padre"}.`);
        }
        payload[meta.parentKey] = form.parent_id;
      }

      if (editingId) {
        await updateCatalogItem(entity, editingId, payload);
        setFeedback("Registro actualizado correctamente.");
      } else {
        await createCatalogItem(entity, payload);
        setFeedback("Registro creado correctamente.");
      }

      await reload();
      resetForm();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "No se pudo guardar el registro.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (itemId: string) => {
    const shouldDelete = window.confirm("Confirma eliminar este registro? Esta accion no se puede deshacer.");
    if (!shouldDelete) {
      return;
    }

    setBusyDeleteId(itemId);
    setFeedback(null);
    setSubmitError(null);

    try {
      await deleteCatalogItem(entity, itemId);
      if (editingId === itemId) {
        resetForm();
      }
      setFeedback("Registro eliminado correctamente.");
      await reload();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "No se pudo eliminar el registro.");
    } finally {
      setBusyDeleteId(null);
    }
  };

  if (!adminUser) {
    return (
      <section className="page-shell">
        <PageHeader title="Catalogos" description="Gestion de maestros operativos." actionLabel="Volver" actionTo="/dashboard?view=admin" />
        <section className="panel warning">
          <h2>Acceso restringido</h2>
          <p>Necesitas perfil administrador para gestionar catalogos.</p>
          <Link className="button button-secondary" to="/dashboard?view=admin">
            Volver al panel admin
          </Link>
        </section>
      </section>
    );
  }

  return (
    <section className="page-shell">
      <section className="user-sticky-shell">
        <PageHeader title={meta.title} description={meta.description} actionLabel="Volver a tarjetas" actionTo="/dashboard?view=admin" compact />

        <section className="toolbar-card user-toolbar user-toolbar-compact">
          <select value={entity} onChange={(event) => changeEntity(event.target.value as CatalogEntity)}>
            {ENTITY_META.map((option) => (
              <option key={option.key} value={option.key}>
                {option.title}
              </option>
            ))}
          </select>

          <input
            name="search"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por codigo o nombre"
            type="search"
            value={search}
          />

          <label className="checkbox-inline">
            <input checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} type="checkbox" />
            Incluir inactivos
          </label>

          <button className="button button-secondary" onClick={resetForm} type="button">
            Nuevo registro
          </button>
        </section>
      </section>

      {feedback ? <div className="panel">{feedback}</div> : null}
      {submitError ? <div className="panel danger">{submitError}</div> : null}

      <DataState loading={loading} error={error} onRetry={reload}>
        <div className="user-management-grid">
          <section className="panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Formulario</p>
                <h2>{editingId ? "Editar registro" : "Nuevo registro"}</h2>
              </div>
              <StatusBadge value={form.is_active ? "active" : "inactive"} compact />
            </div>

            <form className="form-grid" onSubmit={handleSubmit}>
              <label className="field">
                <span>Codigo</span>
                <input name="code" onChange={handleInputChange} required type="text" value={form.code} />
              </label>

              <label className="field">
                <span>Nombre</span>
                <input name="name" onChange={handleInputChange} required type="text" value={form.name} />
              </label>

              <label className="field">
                <span>Orden de visualizacion</span>
                <input min={0} name="display_order" onChange={handleInputChange} required type="number" value={form.display_order} />
              </label>

              {meta.parentKey ? (
                <label className="field">
                  <span>{meta.parentLabel}</span>
                  <select name="parent_id" onChange={handleInputChange} required value={form.parent_id}>
                    <option value="">Seleccionar...</option>
                    {parentOptions.map((option) => (
                      <option key={option.id} value={option.id}>{`${option.code} - ${option.name}`}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="field" />
              )}

              <div className="field user-checkbox-group">
                <label className="checkbox-inline">
                  <input checked={form.is_active} name="is_active" onChange={handleInputChange} type="checkbox" />
                  Activo
                </label>
              </div>

              <div className="field-span-2 form-actions">
                <button className="button button-primary" disabled={submitting} type="submit">
                  {submitting ? "Guardando..." : editingId ? "Guardar cambios" : "Crear registro"}
                </button>
                {editingId ? (
                  <button className="button button-secondary" onClick={resetForm} type="button">
                    Cancelar edicion
                  </button>
                ) : null}
              </div>
            </form>
          </section>

          <section className="panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Directorio</p>
                <h2>Registros ({data?.total || 0})</h2>
              </div>
            </div>

            <div className="stack-list user-list-scroll">
              {items.length === 0 ? (
                <p className="muted-copy">No hay registros para los filtros seleccionados.</p>
              ) : (
                items.map((item) => (
                  <article className="list-card" key={item.id}>
                    <div>
                      <strong>{`${item.code} - ${item.name}`}</strong>
                      {itemParentLabel(item) ? <p>{itemParentLabel(item)}</p> : null}
                      <small>Orden: {item.display_order}</small>
                      <small>Actualizado: {formatDateTime(item.updated_at)}</small>
                    </div>
                    <div className="badge-stack align-end">
                      <StatusBadge value={item.is_active ? "active" : "inactive"} compact />
                      <div className="user-row-actions">
                        <button className="button button-secondary" onClick={() => handleEdit(item)} type="button">
                          Editar
                        </button>
                        <button
                          className="button button-ghost"
                          disabled={busyDeleteId === item.id}
                          onClick={() => void handleDelete(item.id)}
                          type="button"
                        >
                          {busyDeleteId === item.id ? "Eliminando..." : "Eliminar"}
                        </button>
                      </div>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
      </DataState>
    </section>
  );
}





