from datetime import date

from rest_framework.exceptions import ValidationError


def parse_iso_date_parameter(value: str, *, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            {field_name: "La fecha debe tener formato YYYY-MM-DD."}
        ) from exc
