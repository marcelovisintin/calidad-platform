import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { createCatalogItem, deleteCatalogItem, fetchCatalogItems, updateCatalogItem } from "../../../api/catalog";
import type { CatalogEntity, CatalogManagementItem } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { formatDateTime } from "../../../app/utils";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { PaginationControls } from "../../../components/PaginationControls";
import { StatusBadge } from "../../../components/StatusBadge";
import { TabbedFilters } from "../../../components/TabbedFilters";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

type FormState = {
  code: string;
  name: string;
  display_order: string;
  is_active: boolean;
  parent_id: string;
  requires_classification_responsible: boolean;
  closes_anomaly_as_invalid: boolean;
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
    title: "Sectores",
    description: "Sectores o subsectores de trabajo disponibles para el registro.",
    parentEntity: "sites",
    parentLabel: "Area",
    parentKey: "site_id",
  },
  {
    key: "lines",
    title: "Lineas",
    description: "Lineas o puestos productivos utilizados en el sector.",
    parentEntity: "areas",
    parentLabel: "Sector",
    parentKey: "area_id",
  },
  {
    key: "anomaly-types",
    title: "Tipos de desvio",
    description: "Catalogo de defectos, desvios o eventos de calidad.",
  },
  {
    key: "anomaly-origins",
    title: "Asignado a",
    description: "Catalogo de asignaciones asociadas a la anomalia.",
  },
  {
    key: "severities",
    title: "Criterios de Revisión de hallazgos",
    description: "Criterios usados para la Revisión de hallazgos de cada anomalia.",
  },
  {
    key: "priorities",
    title: "Orden operativo",
    description: "Criterios internos de ordenamiento operativo y tratamiento.",
  },
  {
    key: "action-types",
    title: "Tipos de accion",
    description: "Contencion, correctiva, preventiva o mejora.",
  },
  {
    key: "order-types",
    title: "Tipos de ordenes afectadas",
    description: "Tipos de orden que pueden vincularse con una anomalia, por ejemplo OP, OF u OM.",
  },
];

const EMPTY_FORM: FormState = {
  code: "",
  name: "",
  display_order: "0",
  is_active: true,
  parent_id: "",
  requires_classification_responsible: true,
  closes_anomaly_as_invalid: false,
};

const DIRECTORY_PAGE_SIZE = 30;

function resolveEntity(raw: string | null): CatalogEntity {
  const valid = new Set(ENTITY_META.map((item) => item.key));
  if (raw && valid.has(raw as CatalogEntity)) {
    return raw as CatalogEntity;
  }
  return "sites";
}

export function CatalogManagementPage() {
  usePageTitle("Catalogos");
  const { user } = useAuth();
  const adminUser = isAdminUser(user);

  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
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
        page,
        pageSize: DIRECTORY_PAGE_SIZE,
      }),
      meta.parentEntity
        ? fetchCatalogItems(meta.parentEntity, {
            active: undefined,
            page: 1,
            pageSize: 100,
          })
        : Promise.resolve({ count: 0, next: null, previous: null, results: [] as CatalogManagementItem[] }),
    ]);

    return {
      total: items.count,
      items: items.results,
      parents: parents.results,
    };
  }, [entity, includeInactive, meta.parentEntity, search, page]);

  const parentOptions = data?.parents ?? [];
  const items = data?.items ?? [];

  const changeEntity = (next: CatalogEntity) => {
    setSearchParams({ entity: next });
    setPage(1);
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
      requires_classification_responsible: item.requires_classification_responsible ?? true,
      closes_anomaly_as_invalid: item.closes_anomaly_as_invalid ?? false,
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setFeedback(null);

    try {
      if (entity === "anomaly-origins") {
        const nextOrder = Number(form.display_order || 0);
        const duplicate = items.find((item) => item.display_order === nextOrder && item.id !== editingId);
        if (duplicate) {
          throw new Error(`Ya existe otro registro de Asignado a con orden ${nextOrder}: ${duplicate.code} - ${duplicate.name}.`);
        }
      }

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

      if (entity === "severities") {
        payload.requires_classification_responsible = form.closes_anomaly_as_invalid ? false : form.requires_classification_responsible;
        payload.closes_anomaly_as_invalid = form.closes_anomaly_as_invalid;
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

        <TabbedFilters
          actions={<button className="button button-secondary" onClick={resetForm} type="button">Nuevo registro</button>}
          ariaLabel="Filtros de catalogos"
          onClear={() => { setSearch(""); setIncludeInactive(false); setPage(1); }}
          items={[
            {
              id: "catalog",
              label: "Catalogo",
              active: false,
              content: (
                <select aria-label="Catalogo" value={entity} onChange={(event) => changeEntity(event.target.value as CatalogEntity)}>
                  {ENTITY_META.map((option) => <option key={option.key} value={option.key}>{option.title}</option>)}
                </select>
              ),
            },
            {
              id: "search",
              label: "Buscar",
              active: Boolean(search),
              content: <input aria-label="Buscar en catalogo" name="search" onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Codigo o nombre" type="search" value={search} />,
            },
            {
              id: "status",
              label: "Estado",
              active: includeInactive,
              content: (
                <div className="tabbed-filter-toggle">
                  <label className="checkbox-inline">
                    <input checked={includeInactive} onChange={(event) => { setIncludeInactive(event.target.checked); setPage(1); }} type="checkbox" />
                    Incluir registros inactivos
                  </label>
                </div>
              ),
            },
          ]}
        />
      </section>

      {feedback ? <div className="panel">{feedback}</div> : null}
      {submitError ? <div className="panel danger">{submitError}</div> : null}

      <DataState loading={loading} error={error} onRetry={reload}>
        <div className="user-management-grid directory-workspace">
          <section className="panel directory-form-panel">
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

              {entity === "severities" ? (
                <div className="field-span-2 user-checkbox-group">
                  <label className="checkbox-inline">
                    <input
                      checked={form.requires_classification_responsible}
                      disabled={form.closes_anomaly_as_invalid}
                      name="requires_classification_responsible"
                      onChange={handleInputChange}
                      type="checkbox"
                    />
                    Requiere responsable al confirmar
                  </label>
                  <label className="checkbox-inline">
                    <input
                      checked={form.closes_anomaly_as_invalid}
                      name="closes_anomaly_as_invalid"
                      onChange={(event) => {
                        const checked = event.target.checked;
                        setForm((current) => ({
                          ...current,
                          closes_anomaly_as_invalid: checked,
                          requires_classification_responsible: checked ? false : current.requires_classification_responsible,
                        }));
                      }}
                      type="checkbox"
                    />
                    Cierra como Invalida
                  </label>
                </div>
              ) : null}

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

          <section className="panel directory-panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Directorio</p>
                <h2>Registros ({data?.total || 0})</h2>
              </div>
            </div>

            <div className="stack-list user-list-scroll directory-list catalog-directory-list">
              {items.length === 0 ? (
                <p className="muted-copy">No hay registros para los filtros seleccionados.</p>
              ) : (
                items.map((item) => (
                  <article className="list-card" key={item.id}>
                    <div className="directory-record-copy">
                      <div className="directory-record-primary catalog-record-title">
                        <strong>{`${item.code} - ${item.name}`}</strong>
                      </div>
                      <div className="directory-record-secondary">
                        <small>Actualizado: {formatDateTime(item.updated_at)}</small>
                      </div>
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
            <PaginationControls
              alwaysVisible
              page={page}
              pageSize={DIRECTORY_PAGE_SIZE}
              totalCount={data?.total || 0}
              onPageChange={setPage}
              disabled={loading}
            />
          </section>
        </div>
      </DataState>
    </section>
  );
}





