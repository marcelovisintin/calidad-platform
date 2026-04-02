import type { AnomalyStatusHistory } from "../api/types";
import { formatDateTime } from "../app/utils";
import { StatusBadge } from "./StatusBadge";

type TimelineProps = {
  items: AnomalyStatusHistory[];
};

export function Timeline({ items }: TimelineProps) {
  return (
    <ol className="timeline">
      {items.map((item) => (
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
              {item.changed_by?.full_name ? ` · ${item.changed_by.full_name}` : ""}
            </small>
          </div>
        </li>
      ))}
    </ol>
  );
}
