from django.db import migrations
from django.db.models import F, Q
from django.utils import timezone


def correct_observation_verifier_roles(apps, schema_editor):
    database = schema_editor.connection.alias
    Participant = apps.get_model("anomalies", "AnomalyParticipant")
    InitialVerification = apps.get_model("anomalies", "AnomalyInitialVerification")
    EffectivenessCheck = apps.get_model("anomalies", "AnomalyEffectivenessCheck")
    ImmediateAction = apps.get_model("anomalies", "AnomalyImmediateAction")
    Treatment = apps.get_model("actions", "Treatment")
    AuditEvent = apps.get_model("audit", "AuditEvent")
    candidates = Participant.objects.using(database).filter(
        role="verifier", note="Registra y verifica cierre por Observacion.",
    )
    for participant in candidates.iterator():
        has_initial = InitialVerification.objects.using(database).filter(
            anomaly_id=participant.anomaly_id, verified_by_id=participant.user_id,
        ).exists()
        has_effectiveness = EffectivenessCheck.objects.using(database).filter(
            anomaly_id=participant.anomaly_id, verified_by_id=participant.user_id,
        ).exists()
        has_observation_validation = ImmediateAction.objects.using(database).filter(
            anomaly_id=participant.anomaly_id, responsible_id=participant.user_id,
            effectiveness_verified_at__isnull=False,
        ).exists()
        linked_treatments = Treatment.objects.using(database).filter(
            Q(primary_anomaly_id=participant.anomaly_id)
            | Q(anomaly_links__anomaly_id=participant.anomaly_id)
        ).values("pk")
        has_treatment_validation = AuditEvent.objects.using(database).filter(
            entity_type="actions.treatment", entity_id__in=linked_treatments,
            action="treatment.effectiveness_validated", actor_id=participant.user_id,
        ).exists()
        before = {
            "participant_id": str(participant.pk), "user_id": str(participant.user_id),
            "role": participant.role, "note": participant.note,
        }
        if has_initial or has_effectiveness or has_observation_validation or has_treatment_validation:
            note = "Participa como verificador de la etapa inicial." if has_initial else "Realizó una verificación de eficacia."
            Participant.objects.using(database).filter(pk=participant.pk).update(
                note=note, updated_at=timezone.now(), row_version=F("row_version") + 1,
            )
            after = {"participant_id": str(participant.pk), "role": "verifier", "note": note}
        else:
            participant.delete(using=database)
            after = {"removed": True, "reason": "El rol fue asignado al cargar la observación, sin verificación realizada."}
        AuditEvent.objects.using(database).create(
            entity_type="anomalies.anomaly", entity_id=participant.anomaly_id,
            action="anomaly.participant_role_corrected", before_data=before, after_data=after,
            request_id="migration:0022_correct_observation_verifier_roles",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("anomalies", "0021_observation_action_evidences"),
        ("actions", "0020_treatment_analysis_methods"),
        ("audit", "0001_initial"),
    ]

    operations = [migrations.RunPython(correct_observation_verifier_roles, migrations.RunPython.noop)]
