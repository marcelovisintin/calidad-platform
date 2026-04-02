type DataStateProps = {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  onRetry?: () => void;
  children: React.ReactNode;
};

export function DataState({
  loading = false,
  error,
  empty = false,
  emptyTitle = "Sin datos",
  emptyDescription = "Todavia no hay informacion para mostrar.",
  onRetry,
  children,
}: DataStateProps) {
  if (loading) {
    return <div className="panel muted">Cargando informacion...</div>;
  }

  if (error) {
    return (
      <div className="panel danger">
        <strong>No se pudo cargar la informacion.</strong>
        <p>{error}</p>
        {onRetry ? (
          <button className="button button-secondary" onClick={onRetry} type="button">
            Reintentar
          </button>
        ) : null}
      </div>
    );
  }

  if (empty) {
    return (
      <div className="panel muted">
        <strong>{emptyTitle}</strong>
        <p>{emptyDescription}</p>
      </div>
    );
  }

  return <>{children}</>;
}
