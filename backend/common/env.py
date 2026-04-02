from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


class ImproperEnvironmentError(RuntimeError):
    """Error de configuracion de entorno."""


def env(key: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and (value is None or value == ""):
        raise ImproperEnvironmentError(f"La variable de entorno '{key}' es obligatoria.")
    if value is None:
        raise ImproperEnvironmentError(f"La variable de entorno '{key}' no esta definida.")
    return value


def env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ImproperEnvironmentError(
            f"La variable de entorno '{key}' debe ser un entero, se recibio: '{value}'."
        )


def env_list(key: str, default: Iterable[str] | None = None, separator: str = ",") -> list[str]:
    value = os.getenv(key)
    if value is None:
        return [item for item in (default or []) if item]
    return [item.strip() for item in value.split(separator) if item.strip()]


def env_path(key: str, default: str | Path, base_dir: str | Path | None = None) -> Path:
    raw_value = Path(os.getenv(key, str(default))).expanduser()
    if raw_value.is_absolute():
        return raw_value.resolve()
    if base_dir is not None:
        return (Path(base_dir) / raw_value).resolve()
    return raw_value.resolve()
