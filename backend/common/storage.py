from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from django.utils.text import slugify



def _build_upload_path(section: str, parent_id: object, filename: str) -> str:
    original = Path(filename)
    stem = slugify(original.stem) or "file"
    suffix = original.suffix.lower()
    return f"{section}/{parent_id}/{uuid4().hex}-{stem}{suffix}"



def anomaly_attachment_upload_to(instance, filename: str) -> str:
    anomaly_id = getattr(instance, "anomaly_id", None) or "unassigned"
    return _build_upload_path("anomalies", anomaly_id, filename)



def action_evidence_upload_to(instance, filename: str) -> str:
    action_item_id = getattr(instance, "action_item_id", None) or "unassigned"
    return _build_upload_path("actions", action_item_id, filename)



def treatment_evidence_upload_to(instance, filename: str) -> str:
    treatment_id = getattr(instance, "treatment_id", None) or "unassigned"
    return _build_upload_path("treatments", treatment_id, filename)



def treatment_task_evidence_upload_to(instance, filename: str) -> str:
    task_id = getattr(instance, "treatment_task_id", None) or "unassigned"
    return _build_upload_path("treatment-tasks", task_id, filename)
