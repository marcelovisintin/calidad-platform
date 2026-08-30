import { Link } from "react-router-dom";
import type { ReactNode } from "react";

type PageHeaderProps = {
  title: string;
  description?: string;
  actionLabel?: string;
  actionTo?: string;
  action?: ReactNode;
  compact?: boolean;
};

export function PageHeader({ title, description, actionLabel, actionTo, action, compact = true }: PageHeaderProps) {
  return (
    <header className={`page-header${compact ? " compact" : ""}`}>
      <div>
        <p className="eyebrow">Operacion diaria</p>
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {action ?? (actionLabel && actionTo ? (
        <Link className="button button-primary" to={actionTo}>
          {actionLabel}
        </Link>
      ) : null)}
    </header>
  );
}
