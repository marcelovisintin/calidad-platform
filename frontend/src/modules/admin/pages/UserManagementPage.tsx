import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { createUser, deleteUser, fetchUsers, updateUser } from "../../../api/accounts";
import { fetchCatalogBootstrap } from "../../../api/catalog";
import type { UserDirectoryItem } from "../../../api/types";
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

type AccessLevel = "usuario_activo" | "mando_medio_activo" | "administrador" | "desarrollador";

type UserFormState = {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  employee_code: string;
  phone: string;
  photo: File | null;
  access_level: AccessLevel;
  primary_sector: string;
  is_active: boolean;
  email_notifications_enabled: boolean;
  password: string;
  password_confirmation: string;
};

type IssuedCredential = {
  username: string;
  password: string;
};

const accessLevelOptions: Array<{ value: AccessLevel; label: string }> = [
  { value: "usuario_activo", label: "Usuario activo" },
  { value: "mando_medio_activo", label: "Mando medio activo" },
  { value: "administrador", label: "Administrador" },
  { value: "desarrollador", label: "Desarrollador" },
];

const emptyForm: UserFormState = {
  username: "",
  email: "",
  first_name: "",
  last_name: "",
  employee_code: "",
  phone: "",
  photo: null,
  access_level: "usuario_activo",
  primary_sector: "",
  is_active: true,
  email_notifications_enabled: false,
  password: "",
  password_confirmation: "",
};

const DIRECTORY_PAGE_SIZE = 30;

const temporaryPasswordDigits = "0123456789";

function secureRandomIndex(maximum: number) {
  const values = new Uint32Array(1);
  crypto.getRandomValues(values);
  return values[0] % maximum;
}

function generateSecureTemporaryPassword() {
  const characters: string[] = [];
  while (characters.length < 8) {
    characters.push(temporaryPasswordDigits[secureRandomIndex(temporaryPasswordDigits.length)]);
  }

  return characters.join("");
}

function fallbackCopy(text: string) {
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.style.position = "fixed";
  textArea.style.opacity = "0";
  document.body.appendChild(textArea);
  textArea.select();
  const copied = document.execCommand("copy");
  textArea.remove();
  return copied;
}

function resolveAccessLevel(item: UserDirectoryItem): AccessLevel {
  if (item.access_level) {
    return item.access_level;
  }
  if (item.is_staff) {
    return "administrador";
  }
  return "usuario_activo";
}

export function UserManagementPage() {
  usePageTitle("Usuarios");
  const { user } = useAuth();
  const adminUser = isAdminUser(user);

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [includeInactive, setIncludeInactive] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<UserFormState>(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [busyDeleteId, setBusyDeleteId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showTemporaryPassword, setShowTemporaryPassword] = useState(false);
  const [issuedCredential, setIssuedCredential] = useState<IssuedCredential | null>(null);
  const [credentialCopied, setCredentialCopied] = useState(false);

  const { data, loading, error, reload } = useAsyncTask(async () => {
    const [users, bootstrap] = await Promise.all([
      fetchUsers({
        active: includeInactive ? undefined : true,
        q: search,
        page,
        pageSize: DIRECTORY_PAGE_SIZE,
      }),
      fetchCatalogBootstrap(),
    ]);

    return {
      users,
      areas: bootstrap.areas,
    };
  }, [search, includeInactive, page]);

  const areas = data?.areas ?? [];
  const users = data?.users.results ?? [];

  const editingUser = useMemo(() => users.find((item) => item.id === editingId) ?? null, [editingId, users]);

  const resetForm = () => {
    setEditingId(null);
    setForm(emptyForm);
    setSubmitError(null);
    setShowTemporaryPassword(false);
  };

  const startNewUser = () => {
    resetForm();
    setFeedback(null);
    setIssuedCredential(null);
    setCredentialCopied(false);
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

  const handlePhotoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setForm((current) => ({ ...current, photo: file }));
  };

  const handleEdit = (item: UserDirectoryItem) => {
    setEditingId(item.id);
    setFeedback(null);
    setSubmitError(null);
    setIssuedCredential(null);
    setCredentialCopied(false);
    setForm({
      username: item.username,
      email: item.email,
      first_name: item.first_name || "",
      last_name: item.last_name || "",
      employee_code: item.employee_code || "",
      phone: item.phone || "",
      photo: null,
      access_level: resolveAccessLevel(item),
      primary_sector: item.primary_sector_id || item.sector?.id || "",
      is_active: item.is_active,
      email_notifications_enabled: item.email_notifications_enabled,
      password: "",
      password_confirmation: "",
    });
  };

  const handleGenerateTemporaryPassword = () => {
    const password = generateSecureTemporaryPassword();
    setForm((current) => ({
      ...current,
      password,
      password_confirmation: password,
    }));
    setShowTemporaryPassword(true);
    setSubmitError(null);
  };

  const handleCopyIssuedCredential = async () => {
    if (!issuedCredential) {
      return;
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(issuedCredential.password);
      } else if (!fallbackCopy(issuedCredential.password)) {
        throw new Error("No se pudo copiar");
      }
      setCredentialCopied(true);
    } catch {
      setCredentialCopied(fallbackCopy(issuedCredential.password));
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);
    setFeedback(null);
    setIssuedCredential(null);
    setCredentialCopied(false);

    const temporaryPassword = form.password.trim();
    const passwordConfirmation = form.password_confirmation.trim();
    if (temporaryPassword !== passwordConfirmation) {
      setSubmitError("La confirmación no coincide con la contraseña provisoria.");
      return;
    }

    setSubmitting(true);

    try {
      const payload = {
        username: form.username.trim(),
        email: form.email.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        employee_code: form.employee_code.trim(),
        phone: form.phone.trim(),
        photo: form.photo || undefined,
        access_level: form.access_level,
        primary_sector: form.primary_sector || null,
        is_active: form.is_active,
        email_notifications_enabled: form.email_notifications_enabled,
        password: temporaryPassword || undefined,
        password_confirmation: temporaryPassword ? passwordConfirmation : undefined,
      };

      if (editingId) {
        await updateUser(editingId, payload);
        if (temporaryPassword) {
          setIssuedCredential({ username: payload.username, password: temporaryPassword });
          setFeedback("Contraseña provisoria asignada correctamente. El cambio será obligatorio en el próximo ingreso.");
        } else {
          setFeedback("Usuario actualizado correctamente.");
        }
      } else {
        const createdUser = await createUser(payload);
        const issuedPassword = createdUser.initial_password || temporaryPassword;
        if (issuedPassword) {
          setIssuedCredential({ username: payload.username, password: issuedPassword });
        }
        setFeedback("Usuario creado correctamente. Deberá cambiar la contraseña provisoria en su primer ingreso.");
      }

      await reload();
      resetForm();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "No se pudo guardar el usuario.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (userId: string) => {
    const shouldDelete = window.confirm("Confirma eliminar este usuario? Esta accion no se puede deshacer.");
    if (!shouldDelete) {
      return;
    }

    setBusyDeleteId(userId);
    setSubmitError(null);
    setFeedback(null);
    setIssuedCredential(null);
    setCredentialCopied(false);

    try {
      await deleteUser(userId);
      if (editingId === userId) {
        resetForm();
      }
      setFeedback("Usuario eliminado correctamente.");
      await reload();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "No se pudo eliminar el usuario.");
    } finally {
      setBusyDeleteId(null);
    }
  };

  if (!adminUser) {
    return (
      <section className="page-shell">
        <PageHeader
          title="Usuarios"
          description="Gestion administrativa de cuentas del sistema."
          actionLabel="Volver a tarjetas"
          actionTo="/dashboard?view=admin"
        />
        <section className="panel warning">
          <h2>Acceso restringido</h2>
          <p>Necesitas perfil administrador para crear, editar o eliminar usuarios.</p>
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
        <PageHeader title="Usuarios" actionLabel="Volver a tarjetas" actionTo="/dashboard?view=admin" compact />

        <TabbedFilters
          actions={(
            <>
              <button className="button button-secondary" onClick={startNewUser} type="button">Nuevo usuario</button>
              <Link className="button button-secondary" to="/management/users/import">Importacion masiva</Link>
            </>
          )}
          ariaLabel="Filtros de usuarios"
          onClear={() => { setSearch(""); setIncludeInactive(false); setPage(1); }}
          items={[
            {
              id: "search",
              label: "Buscar usuario",
              active: Boolean(search),
              content: <input aria-label="Buscar usuario" name="search" onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Usuario, email, nombre o legajo" type="search" value={search} />,
            },
            {
              id: "status",
              label: "Estado",
              active: includeInactive,
              content: (
                <div className="tabbed-filter-toggle">
                  <label className="checkbox-inline">
                    <input checked={includeInactive} onChange={(event) => { setIncludeInactive(event.target.checked); setPage(1); }} type="checkbox" />
                    Incluir usuarios inactivos
                  </label>
                </div>
              ),
            },
          ]}
        />
      </section>

      {feedback ? <div className="panel">{feedback}</div> : null}
      {submitError ? <div className="panel danger">{submitError}</div> : null}
      {issuedCredential ? (
        <section className="panel success temporary-credential-panel" role="status">
          <div>
            <strong>Credencial provisoria confirmada</strong>
            <p>
              Usuario: <b>{issuedCredential.username}</b>
            </p>
            <code>{issuedCredential.password}</code>
            <small>Se muestra una sola vez. Entrégala al usuario por un medio seguro.</small>
          </div>
          <div className="form-actions">
            <button className="button button-primary" onClick={() => void handleCopyIssuedCredential()} type="button">
              {credentialCopied ? "Copiada" : "Copiar contraseña"}
            </button>
            <button className="button button-secondary" onClick={() => setIssuedCredential(null)} type="button">
              Cerrar
            </button>
          </div>
        </section>
      ) : null}

      <DataState loading={loading} error={error} onRetry={reload}>
        <div className="user-management-grid directory-workspace">
          <section className="panel directory-form-panel">
            <div className="section-head compact">
              <div>
                <p className="eyebrow">Formulario</p>
                <h2>{editingId ? "Editar usuario" : "Nuevo usuario"}</h2>
              </div>
              {editingUser ? <StatusBadge value={editingUser.is_active ? "active" : "inactive"} compact /> : null}
            </div>

            <form className="form-grid" onSubmit={handleSubmit}>
              <label className="field">
                <span>Usuario</span>
                <input name="username" onChange={handleInputChange} required type="text" value={form.username} />
              </label>
              <label className="field">
                <span>Email</span>
                <input name="email" onChange={handleInputChange} required type="email" value={form.email} />
              </label>
              <label className="field">
                <span>Nombre</span>
                <input name="first_name" onChange={handleInputChange} type="text" value={form.first_name} />
              </label>
              <label className="field">
                <span>Apellido</span>
                <input name="last_name" onChange={handleInputChange} type="text" value={form.last_name} />
              </label>
              <label className="field">
                <span>Legajo</span>
                <input name="employee_code" onChange={handleInputChange} type="text" value={form.employee_code} />
              </label>
              <label className="field">
                <span>Celular</span>
                <input name="phone" onChange={handleInputChange} type="tel" value={form.phone} placeholder="+54 9 11 1234-5678" />
              </label>
              <label className="field field-span-2">
                <span>Foto del usuario</span>
                <input accept="image/*" name="photo" onChange={handlePhotoChange} type="file" />
                <small>
                  {form.photo
                    ? `Lista para cargar: ${form.photo.name}`
                    : editingUser?.photo_url
                      ? "Foto actual cargada. Selecciona otra imagen para reemplazarla."
                      : "Se mostrara en la etiqueta superior derecha."}
                </small>
              </label>
              <label className="field">
                <span>Nivel de acceso</span>
                <select name="access_level" onChange={handleInputChange} value={form.access_level}>
                  {accessLevelOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Sector principal</span>
                <select name="primary_sector" onChange={handleInputChange} value={form.primary_sector}>
                  <option value="">Sin asignar</option>
                  {areas.map((item) => (
                    <option key={item.id} value={item.id}>{`${item.code} - ${item.name}`}</option>
                  ))}
                </select>
              </label>
              <div className="field field-span-2 temporary-password-card">
                <div className="section-head compact">
                  <div>
                    <span>Contraseña provisoria</span>
                    <small>
                      {editingId
                        ? "Déjala vacía para conservar la actual. Si asignas otra, el cambio será obligatorio al ingresar."
                        : "Déjala vacía para que el servidor genere una clave segura automáticamente."}
                    </small>
                  </div>
                  <button className="button button-secondary" onClick={handleGenerateTemporaryPassword} type="button">
                    Generar numérica
                  </button>
                </div>
                <div className="temporary-password-grid">
                  <label className="field">
                    <span>Contraseña</span>
                    <input
                      autoComplete="new-password"
                      minLength={8}
                      name="password"
                      onChange={handleInputChange}
                      placeholder="8 caracteres o más"
                      type={showTemporaryPassword ? "text" : "password"}
                      value={form.password}
                    />
                  </label>
                  <label className="field">
                    <span>Confirmar contraseña</span>
                    <input
                      autoComplete="new-password"
                      minLength={8}
                      name="password_confirmation"
                      onChange={handleInputChange}
                      placeholder="Repetir la contraseña"
                      type={showTemporaryPassword ? "text" : "password"}
                      value={form.password_confirmation}
                    />
                  </label>
                </div>
                <div className="temporary-password-help">
                  <small>Puede ser sencilla y solamente numérica, por ejemplo 123456789. El usuario deberá reemplazarla al ingresar.</small>
                  <label className="checkbox-inline">
                    <input
                      checked={showTemporaryPassword}
                      onChange={(event) => setShowTemporaryPassword(event.target.checked)}
                      type="checkbox"
                    />
                    Mostrar contraseña
                  </label>
                </div>
              </div>
              <div className="field user-checkbox-group">
                <label className="checkbox-inline">
                  <input checked={form.is_active} name="is_active" onChange={handleInputChange} type="checkbox" />
                  Cuenta habilitada
                </label>
                <label className="checkbox-inline">
                  <input
                    checked={form.email_notifications_enabled}
                    name="email_notifications_enabled"
                    onChange={handleInputChange}
                    type="checkbox"
                  />
                  Notificación por correo
                </label>
                <small>Desactivada por defecto. Solo habilitarla para usuarios que deban recibir correos.</small>
              </div>

              <div className="field-span-2 form-actions">
                <button className="button button-primary" disabled={submitting} type="submit">
                  {submitting ? "Guardando..." : editingId ? "Guardar cambios" : "Crear usuario"}
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
                <h2>Usuarios ({data?.users.count || 0})</h2>
              </div>
            </div>

            <div className="stack-list user-list-scroll directory-list user-directory-list">
              {users.length === 0 ? (
                <p className="muted-copy">No hay usuarios para los filtros seleccionados.</p>
              ) : (
                users.map((item) => (
                  <article className="list-card" key={item.id}>
                    <div className="directory-record-copy">
                      <div className="directory-record-primary">
                        <strong>{item.full_name || item.username}</strong>
                        <span>{item.email}</span>
                      </div>
                      <div className="directory-record-secondary">
                        <small>
                          {item.username}
                          {item.sector ? ` | ${item.sector.name}` : " | Sin sector"}
                          {item.employee_code ? ` | Legajo ${item.employee_code}` : ""}
                        </small>
                        <small>Ultima actividad: {formatDateTime(item.last_activity_at)}</small>
                      </div>
                    </div>
                    <div className="badge-stack align-end">
                      <StatusBadge value={item.is_active ? "active" : "inactive"} compact />
                      <StatusBadge value={resolveAccessLevel(item)} compact />
                      <StatusBadge
                        value={item.email_notifications_enabled ? "email_notifications_enabled" : "email_notifications_disabled"}
                        compact
                      />
                      {item.must_change_password ? <StatusBadge value="pending" compact /> : null}
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
              totalCount={data?.users.count || 0}
              onPageChange={setPage}
              disabled={loading}
            />
          </section>
        </div>
      </DataState>
    </section>
  );
}
