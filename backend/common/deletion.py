from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError


def delete_or_raise_protected(instance, *, message: str) -> None:
    """Delete an object and surface protected database references as a 400 error."""
    try:
        with transaction.atomic():
            instance.delete()
            if connection.vendor == "postgresql":
                # Legacy archived tables are intentionally absent from Django's
                # model state, so PostgreSQL is the final source of truth.
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    except (ProtectedError, IntegrityError) as exc:
        raise ValidationError({"detail": message}) from exc
