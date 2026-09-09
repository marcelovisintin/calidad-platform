from datetime import datetime

from django.utils import timezone


TERMINAL_STATUSES = {"completed", "closed", "cancelled", "effective", "validated_effective", "resolved"}


def is_overdue(due, status: str, *, finished: bool = False) -> bool:
    """Date commitments remain valid through the end of the configured local day."""
    if not due or finished or status in TERMINAL_STATUSES:
        return False
    if isinstance(due, datetime):
        due = timezone.localtime(due).date() if timezone.is_aware(due) else due.date()
    return due < timezone.localdate()
