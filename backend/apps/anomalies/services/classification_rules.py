from __future__ import annotations

import unicodedata

from django.db.models import Q


IMMEDIATE_TERMS = ("accion inmediata", "inmediata", "immediate")
CLASSIFICATION_EDITABLE_STAGES = {
    "registration",
    "containment",
    "initial_verification",
    "classification",
}


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def is_immediate_action_value(value: str) -> bool:
    normalized = _normalize(value)
    return any(term in normalized for term in IMMEDIATE_TERMS)


def is_immediate_action_anomaly(anomaly) -> bool:
    severity = getattr(anomaly, "severity", None)
    if severity:
        if is_immediate_action_value(getattr(severity, "name", "")):
            return True
        if is_immediate_action_value(getattr(severity, "code", "")):
            return True

    if is_immediate_action_value(getattr(anomaly, "classification_summary", "")):
        return True

    classification = None
    try:
        classification = getattr(anomaly, "classification")
    except Exception:
        classification = None

    if classification and is_immediate_action_value(getattr(classification, "summary", "")):
        return True

    return False


def immediate_action_q(prefix: str = "") -> Q:
    return (
        Q(**{f"{prefix}severity__name__icontains": "inmediata"})
        | Q(**{f"{prefix}severity__code__icontains": "inmediata"})
        | Q(**{f"{prefix}classification_summary__icontains": "accion inmediata"})
        | Q(**{f"{prefix}classification_summary__icontains": "acción inmediata"})
        | Q(**{f"{prefix}classification__summary__icontains": "accion inmediata"})
        | Q(**{f"{prefix}classification__summary__icontains": "acción inmediata"})
    )


def stage_allows_classification_change(anomaly) -> bool:
    return (getattr(anomaly, "current_stage", "") or "") in CLASSIFICATION_EDITABLE_STAGES


def can_modify_classification(anomaly) -> bool:
    if not stage_allows_classification_change(anomaly):
        return False

    if getattr(anomaly, "severity_id", None) is None:
        return True

    if bool(getattr(anomaly, "classification_change_unlocked", False)):
        return True

    return int(getattr(anomaly, "classification_change_count", 0) or 0) < 1


def can_unlock_classification_change(anomaly) -> bool:
    if not stage_allows_classification_change(anomaly):
        return False

    if getattr(anomaly, "severity_id", None) is None:
        return False

    if bool(getattr(anomaly, "classification_change_unlocked", False)):
        return False

    return int(getattr(anomaly, "classification_change_count", 0) or 0) >= 1
