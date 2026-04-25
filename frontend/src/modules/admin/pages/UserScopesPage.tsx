import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchUserAccessOptions,
  fetchUserAccessProfile,
  fetchUsers,
  updateUserAccessProfile,
} from "../../../api/accounts";
import type { AccessLevelOption, UserAccessProfile, UserDirectoryItem } from "../../../api/types";
import { isAdminUser } from "../../../app/access";
import { useAuth } from "../../../app/providers/AuthProvider";
import { DataState } from "../../../components/DataState";
import { PageHeader } from "../../../components/PageHeader";
import { StatusBadge } from "../../../components/StatusBadge";
import { useAsyncTask } from "../../../hooks/useAsyncTask";
import { usePageTitle } from "../../../hooks/usePageTitle";

type ScopeDraft = {
  access_level: AccessLevelOption["value"];
  role: string;
  manual_scope_keys: string[];
};

const emptyDraft: ScopeDraft = {
  access_level: "usuario_activo",
  role: "",
  manual_scope_keys: [],
};

function userLabel(user: UserDirectoryItem) {
  return user.full_name || user.username;
}

function buildDraft(profile: UserAccessProfile): ScopeDraft {
  return {
    access_level: profile.access_level,
    role: profile.role?.id || "",
    manual_scope_keys: profile.manual_scope_keys,
  };
}

export function UserScopesPage() {
  usePageTitle("Alcances de usuario");
  const { user } = useAuth();
  const adminUser = isAdminUser(user);
  const [search, setSearch] = useState("");
  const [selectedUserId, setSelectedUserId] = useState("");
  const [profile, setProfile] = useState<UserAccessProfile | null>(null);
  const [draft, setDraft] = useState<ScopeDraft>(emptyDraft);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const { data, loading, error, reload } = useAsyncTask(async () => {
    const [users, options] = await Promise.all([
      fetchUsers({ active: true, q: search, pageSize: 100 }),
      fetchUserAccessOptions(),
    ]);
    return { users, options };
  }, [search]);

  const users = data?.users.results ?? [];
  const options = data?.options;
  const selectedUser = useMemo(
    () => users.find((item) => item.id === selectedUserId) ?? null,
    [selectedUserId, users],
  );

  useEffect(() => {
    if (!selectedUserId && users.length) {
      setSelectedUserId(users[0].id);
    }
  }, [selectedUserId, users]);

  useEffect(() => {
    if (!selectedUserId) {
      setProfile(null);
      setDraft(emptyDraft);
      return;
    }

    let cancelled = false;
    setProfileLoading(true);
    setProfileError(null);
    setFeedback(null);

    fetchUserAccessProfile(selectedUserId)
      .then((nextProfile) => {
        if (cancelled) {
          return;
        }
        setProfile(nextProfile);
        setDraft(buildDraft(nextProfile));
      })
      .catch((err) => {
        if (!cancelled) {
          setProfileError(err instanceof Error ? err.message : "No se pudo cargar el perfil de alcances.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setProfileLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedUserId]);

  const rolePermissionSet = useMemo(() => new Set(profile?.role_permissions ?? []), [profile?.role_permissions]);

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
  };

  const handleToggleScope = (scopeKey: string, checked: boolean) => {
    setDraft((current) => {
      const nextKeys = new Set(current.manual_scope_keys);
      if (checked) {
        nextKeys.add(scopeKey);
      } else {
        nextKeys.delete(scopeKey);
      }
      return { ...current, manual_scope_keys: Array.from(nextKeys).sort() };
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedUserId) {
      return;
    }

    setSaving(true);
    setProfileError(null);
    setFeedback(null);

    try {
      const updated = await updateUserAccessProfile(selectedUserId, {
        access_level: draft.access_level,
        role: draft.role || null,
        manual_scope_keys: draft.manual_scope_keys,
      });
      setProfile(updated);
      setDraft(buildDraft(updated));
      setFeedback("Alcances de usuario actualizados correctamente.");
      await reload();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "No se pudieron guardar los alcances.");
    } finally {
      setSaving(false);
    }
  };

  if (!adminUser) {
    return (
      <section className="page-shell">
        <PageHeader
          title="Alcances de usuario"
          description="Asignacion administrativa de permisos y alcances."
          actionLabel="Volver a tarjetas"
          actionTo="/dashboard?view=admin"
        />
        <section className="panel warning">
          <h2>Acceso restringido</h2>
          <p>Necesitas perfil administrador para modificar permisos de usuario.</p>
          <Link className="button button-secondary" to="/dashboard?view=admin">
            Volver al panel admin
          </Link>
        </section>
      </section>
    );
  }

  return (
    <section className="page-shell">
      <PageHeader
        title="Alcances de usuario"
        description="Nivel de acceso, rol y permisos especificos por usuario."
        actionLabel="Volver a tarjetas"
        actionTo="/dashboard?view=admin"
      />

      {feedback ? <div className="panel info">{feedback}</div> : null}
      {profileError ? <div className="panel danger">{profileError}</div> : null}

      <DataState loading={loading} error={error} onRetry={reload}>
        <div className="user-management-grid">
          <section className="panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Usuarios</p>
                <h2>Seleccionar usuario</h2>
              </div>
            </div>
            <div className="toolbar-card compact-toolbar">
              <input onChange={handleSearchChange} placeholder="Buscar usuario, nombre o email" type="search" value={search} />
            </div>
            <div className="stack-list user-list-scroll">
              {users.map((item) => (
                <button
                  className={`list-card selectable-card${selectedUserId === item.id ? " active" : ""}`}
                  key={item.id}
                  onClick={() => setSelectedUserId(item.id)}
                  type="button"
                >
                  <div>
                    <strong>{userLabel(item)}</strong>
                    <p>{item.email}</p>
                    <small>{item.sector ? item.sector.name : "Sin sector principal"}</small>
                  </div>
                  <StatusBadge value={item.access_level} compact />
                </button>
              ))}
              {!users.length ? <p className="muted-copy">No hay usuarios activos para los filtros seleccionados.</p> : null}
            </div>
          </section>

          <section className="panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Perfil</p>
                <h2>{selectedUser ? userLabel(selectedUser) : "Sin usuario"}</h2>
              </div>
              {profile ? <StatusBadge value={profile.access_level} compact /> : null}
            </div>

            {profileLoading ? (
              <div className="skeleton-card">Cargando alcances...</div>
            ) : profile && options ? (
              <form className="form-section" onSubmit={handleSubmit}>
                <dl className="key-grid compact">
                  <div>
                    <dt>Nivel actual</dt>
                    <dd>{options.access_levels.find((item) => item.value === profile.access_level)?.label || profile.access_level}</dd>
                  </div>
                  <div>
                    <dt>Rol actual</dt>
                    <dd>{profile.role ? profile.role.name : "Sin rol asignado"}</dd>
                  </div>
                  <div>
                    <dt>Sector principal</dt>
                    <dd>{profile.primary_sector?.name || "Sin sector principal"}</dd>
                  </div>
                  <div>
                    <dt>Permisos efectivos</dt>
                    <dd>{profile.effective_permissions.length}</dd>
                  </div>
                </dl>

                <div className="form-grid">
                  <label className="field">
                    <span>Nivel de acceso</span>
                    <select
                      onChange={(event) => setDraft((current) => ({ ...current, access_level: event.target.value as ScopeDraft["access_level"] }))}
                      value={draft.access_level}
                    >
                      {options.access_levels.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Rol asignado</span>
                    <select onChange={(event) => setDraft((current) => ({ ...current, role: event.target.value }))} value={draft.role}>
                      <option value="">Sin rol</option>
                      {options.roles.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <section className="form-section nested-form">
                  <div className="section-head compact">
                    <div>
                      <p className="eyebrow">Checklist</p>
                      <h3>Permisos especificos habilitados</h3>
                    </div>
                  </div>
                  <div className="scope-checklist">
                    {options.scope_options.map((scope) => {
                      const checked = draft.manual_scope_keys.includes(scope.key);
                      const inherited = scope.permission_keys.some((permission) => rolePermissionSet.has(permission));
                      return (
                        <label className="scope-check-item" key={scope.key}>
                          <input
                            checked={checked}
                            onChange={(event) => handleToggleScope(scope.key, event.target.checked)}
                            type="checkbox"
                          />
                          <span>
                            <strong>{scope.label}</strong>
                            <small>{scope.description}</small>
                            {inherited ? <em>Incluido por rol</em> : null}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </section>

                <div className="form-actions">
                  <button className="button button-primary" disabled={saving} type="submit">
                    {saving ? "Guardando..." : "Guardar alcances"}
                  </button>
                </div>
              </form>
            ) : (
              <p className="muted-copy">Selecciona un usuario para revisar sus alcances.</p>
            )}
          </section>
        </div>
      </DataState>
    </section>
  );
}
