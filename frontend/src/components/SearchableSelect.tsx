import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

export type SearchableSelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
  searchTerms?: string[];
};

type SearchableSelectProps = {
  ariaLabel?: string;
  autoFocus?: boolean;
  className?: string;
  clearable?: boolean;
  dataTour?: string;
  disabled?: boolean;
  label?: string;
  onChange: (value: string) => void;
  options: readonly SearchableSelectOption[];
  placeholder?: string;
  required?: boolean;
  value: string;
};

function normalize(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export function SearchableSelect({
  ariaLabel,
  autoFocus = false,
  className = "",
  clearable = true,
  dataTour,
  disabled = false,
  label,
  onChange,
  options,
  placeholder = "Seleccionar",
  required = false,
  value,
}: SearchableSelectProps) {
  const generatedId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const selectedOption = options.find((option) => option.value === value);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(selectedOption?.label || "");
  const [activeIndex, setActiveIndex] = useState(0);

  const filteredOptions = useMemo(() => {
    const normalizedQuery = normalize(query);
    if (!normalizedQuery) {
      return options;
    }
    return options.filter((option) => {
      const terms = option.searchTerms?.length ? option.searchTerms : option.label.split(/\s+-\s+/);
      return terms.some((term) => normalize(term).startsWith(normalizedQuery));
    });
  }, [options, query]);

  useEffect(() => {
    if (!open) {
      setQuery(selectedOption?.label || "");
    }
  }, [open, selectedOption?.label]);

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    inputRef.current?.setCustomValidity(required && !value ? "Seleccione una opcion de la lista." : "");
  }, [required, value]);

  const selectOption = (option: SearchableSelectOption) => {
    if (option.disabled) return;
    onChange(option.value);
    setQuery(option.label);
    setOpen(false);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) => Math.min(current + 1, Math.max(0, filteredOptions.length - 1)));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) => Math.max(0, current - 1));
      return;
    }
    if (event.key === "Enter" && open && filteredOptions[activeIndex]) {
      event.preventDefault();
      selectOption(filteredOptions[activeIndex]);
      return;
    }
    if (event.key === "Escape") {
      setOpen(false);
    }
  };

  const listboxId = `${generatedId}-listbox`;

  return (
    <div className={`${className} searchable-select-field`.trim()} data-tour={dataTour} ref={containerRef}>
      {label ? <label htmlFor={generatedId}>{label}</label> : null}
      <div className="searchable-select-control">
        <input
          aria-autocomplete="list"
          aria-label={ariaLabel || label}
          aria-controls={listboxId}
          aria-expanded={open}
          aria-required={required}
          autoComplete="off"
          autoFocus={autoFocus}
          disabled={disabled}
          id={generatedId}
          onChange={(event) => {
            if (value) onChange("");
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setQuery("");
            setOpen(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          ref={inputRef}
          required={required}
          role="combobox"
          value={query}
        />
        <button
          aria-label={`Desplegar ${ariaLabel || label || "opciones"}`}
          className="searchable-select-toggle"
          disabled={disabled}
          onClick={() => {
            setQuery("");
            setOpen((current) => !current);
          }}
          tabIndex={-1}
          type="button"
        >
          ▾
        </button>
      </div>
      {open && !disabled ? (
        <div className="searchable-select-options" id={listboxId} role="listbox">
          {clearable ? <button
            aria-selected={!value}
            className={`searchable-select-option${value ? "" : " selected"}`}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              onChange("");
              setQuery("");
              setOpen(false);
            }}
            role="option"
            type="button"
          >
            {placeholder}
          </button> : null}
          {filteredOptions.map((option, index) => (
            <button
              aria-selected={option.value === value}
              className={`searchable-select-option${index === activeIndex ? " active" : ""}${option.value === value ? " selected" : ""}`}
              disabled={option.disabled}
              key={option.value}
              onClick={() => selectOption(option)}
              onMouseDown={(event) => event.preventDefault()}
              role="option"
              type="button"
            >
              {option.label}
            </button>
          ))}
          {!filteredOptions.length ? <p className="searchable-select-empty">Sin coincidencias</p> : null}
        </div>
      ) : null}
    </div>
  );
}
