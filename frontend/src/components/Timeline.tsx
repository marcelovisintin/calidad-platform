import { useEffect, useMemo, useState } from "react";
import type { AnomalyStatusHistory } from "../api/types";
import { formatDateTime } from "../app/utils";
import { PaginationControls } from "./PaginationControls";
import { StatusBadge } from "./StatusBadge";

type TimelineProps = {
  items: AnomalyStatusHistory[];
};

const PAGE_SIZE = 10;

export function Timeline({ items }: TimelineProps) {
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [items.length]);

  const pagedItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, page]);

  if (!items.length) {
    return <p className="muted-copy">No hay registros en el historial.</p>;
  }

  return (
    <>
      <ol className="timeline">
        {pagedItems.map((item) => (
          <li key={item.id} className="timeline-item">
            <div className="timeline-dot" />
            <div className="timeline-content">
              <div className="timeline-row">
                <StatusBadge value={item.from_stage} compact />
                <span className="timeline-arrow">a</span>
                <StatusBadge value={item.to_stage} compact />
              </div>
              <p className="timeline-comment">{item.comment}</p>
              <small>
                {formatDateTime(item.changed_at)}
                {item.changed_by?.full_name ? ` - ${item.changed_by.full_name}` : ""}
              </small>
            </div>
          </li>
        ))}
      </ol>

      <PaginationControls page={page} totalCount={items.length} pageSize={PAGE_SIZE} onPageChange={setPage} />
    </>
  );
}