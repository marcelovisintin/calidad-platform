import { useMemo } from "react";

type PaginationControlsProps = {
  page: number;
  totalCount: number;
  pageSize?: number;
  disabled?: boolean;
  onPageChange: (page: number) => void;
};

export function PaginationControls({ page, totalCount, pageSize = 10, disabled = false, onPageChange }: PaginationControlsProps) {
  const safePage = Math.max(1, page);

  const state = useMemo(() => {
    const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
    const currentPage = Math.min(safePage, totalPages);
    const start = totalCount > 0 ? (currentPage - 1) * pageSize + 1 : 0;
    const end = totalCount > 0 ? Math.min(totalCount, currentPage * pageSize) : 0;
    return {
      totalPages,
      currentPage,
      start,
      end,
      canPrev: currentPage > 1,
      canNext: currentPage < totalPages,
    };
  }, [pageSize, safePage, totalCount]);

  if (totalCount <= pageSize) {
    return null;
  }

  return (
    <div className="pagination-controls" role="navigation" aria-label="Paginacion">
      <p className="pagination-info">{`Mostrando ${state.start}-${state.end} de ${totalCount}`}</p>
      <div className="pagination-actions">
        <button
          className="button button-secondary"
          type="button"
          disabled={disabled || !state.canPrev}
          onClick={() => onPageChange(state.currentPage - 1)}
        >
          Anterior
        </button>
        <span className="pagination-page">{`Pagina ${state.currentPage} de ${state.totalPages}`}</span>
        <button
          className="button button-secondary"
          type="button"
          disabled={disabled || !state.canNext}
          onClick={() => onPageChange(state.currentPage + 1)}
        >
          Siguiente
        </button>
      </div>
    </div>
  );
}