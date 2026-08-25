import { KeyboardEvent, ReactNode, useEffect, useId, useMemo, useRef, useState } from "react";

export type TabbedFilterItem = {
  id: string;
  label: string;
  active: boolean;
  content: ReactNode;
};

type TabbedFiltersProps = {
  actions?: ReactNode;
  ariaLabel?: string;
  items: TabbedFilterItem[];
  onClear: () => void;
};

export function TabbedFilters({ actions, ariaLabel = "Filtros", items, onClear }: TabbedFiltersProps) {
  const componentId = useId().replace(/:/g, "");
  const [selectedId, setSelectedId] = useState(items[0]?.id ?? "");
  const panelRef = useRef<HTMLDivElement>(null);
  const shouldFocusPanelRef = useRef(false);

  useEffect(() => {
    if (!items.some((item) => item.id === selectedId)) {
      setSelectedId(items[0]?.id ?? "");
    }
  }, [items, selectedId]);

  useEffect(() => {
    if (!shouldFocusPanelRef.current) {
      return;
    }

    shouldFocusPanelRef.current = false;
    panelRef.current?.querySelector<HTMLElement>("input, select, textarea")?.focus();
  }, [selectedId]);

  const selectItem = (itemId: string) => {
    if (itemId === selectedId) {
      panelRef.current?.querySelector<HTMLElement>("input, select, textarea")?.focus();
      return;
    }

    shouldFocusPanelRef.current = true;
    setSelectedId(itemId);
  };

  const selectedItem = items.find((item) => item.id === selectedId) ?? items[0];
  const activeCount = useMemo(() => items.filter((item) => item.active).length, [items]);

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }

    const tabs = Array.from(event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("[role=tab]") ?? []);
    const currentIndex = tabs.indexOf(event.currentTarget);
    if (currentIndex < 0 || tabs.length === 0) {
      return;
    }

    event.preventDefault();
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? tabs.length - 1
        : (currentIndex + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[nextIndex].focus();
    selectItem(tabs[nextIndex].dataset.filterId ?? "");
  };

  if (!selectedItem) {
    return null;
  }

  return (
    <section className="tabbed-filters" aria-label={ariaLabel}>
      <div className="tabbed-filters-tabs" role="tablist" aria-label={ariaLabel}>
        {items.map((item) => {
          const selected = item.id === selectedItem.id;
          return (
            <button
              aria-controls={`${componentId}-panel`}
              aria-label={`${item.label}${item.active ? " (filtro activo)" : ""}`}
              aria-selected={selected}
              className={`tabbed-filter-tab${item.active ? " has-value" : ""}`}
              data-filter-id={item.id}
              id={`${componentId}-${item.id}-tab`}
              key={item.id}
              onClick={() => selectItem(item.id)}
              onKeyDown={handleTabKeyDown}
              role="tab"
              tabIndex={selected ? 0 : -1}
              type="button"
            >
              <span>{item.label}</span>
              {item.active ? <span className="tabbed-filter-dot" aria-hidden="true" /> : null}
            </button>
          );
        })}
      </div>

      <div
        aria-labelledby={`${componentId}-${selectedItem.id}-tab`}
        className="tabbed-filters-panel"
        id={`${componentId}-panel`}
        ref={panelRef}
        role="tabpanel"
      >
        <div className="tabbed-filter-control">{selectedItem.content}</div>
        {actions ? <div className="tabbed-filter-actions">{actions}</div> : null}
        {activeCount > 0 ? (
          <button className="button button-secondary tabbed-filter-clear" onClick={onClear} type="button">
            {`Limpiar filtros (${activeCount})`}
          </button>
        ) : null}
      </div>
    </section>
  );
}
