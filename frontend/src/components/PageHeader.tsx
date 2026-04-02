import { Link } from "react-router-dom";

type PageHeaderProps = {
  title: string;
  description?: string;
  actionLabel?: string;
  actionTo?: string;
  compact?: boolean;
};

export function PageHeader({ title, description, actionLabel, actionTo, compact = false }: PageHeaderProps) {
  return (
    <header className={`page-header${compact ? " compact" : ""}`}>
      <div>
        <p className="eyebrow">Operacion diaria</p>
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actionLabel && actionTo ? (
        <Link className="button button-primary" to={actionTo}>
          {actionLabel}
        </Link>
      ) : null}
    </header>
  );
}
