export function CompanyLogo({ compact = false, inverted = false }: { compact?: boolean; inverted?: boolean }) {
  const className = ["company-logo", compact ? "compact" : "", inverted ? "inverted" : ""].filter(Boolean).join(" ");

  return (
    <div aria-label="Schneider" className={className} role="img">
      <span className="company-logo-text">SCHNEIDER</span>
      <span className="company-logo-bar" />
    </div>
  );
}
