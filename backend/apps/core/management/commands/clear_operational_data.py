from __future__ import annotations

from collections import OrderedDict

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.actions.models import (
    ActionEvidence,
    ActionPlan,
    Treatment,
    TreatmentEvidence,
    TreatmentLearnedLessonEvidence,
    TreatmentTaskEvidence,
)
from apps.anomalies.models import Anomaly, AnomalyAttachment, AnomalyCodeReservation
from apps.audit.models import AuditEvent
from apps.notifications.models import Notification


FILE_MODELS = (
    (AnomalyAttachment, "file"),
    (ActionEvidence, "file"),
    (TreatmentEvidence, "file"),
    (TreatmentTaskEvidence, "file"),
    (TreatmentLearnedLessonEvidence, "file"),
)

ROOT_MODELS = OrderedDict(
    (
        ("eventos de auditoria", AuditEvent),
        ("notificaciones y pendientes", Notification),
        ("tratamientos", Treatment),
        ("planes de accion", ActionPlan),
        ("reservas de codigos de anomalia", AnomalyCodeReservation),
        ("anomalias", Anomaly),
    )
)


def _catalog_counts() -> dict[str, int]:
    return {
        model._meta.label_lower: model.objects.count()
        for model in apps.get_app_config("catalog").get_models()
    }


def _protected_counts() -> dict[str, object]:
    return {
        "users": User.objects.count(),
        "catalog": _catalog_counts(),
    }


def _operational_counts() -> dict[str, int]:
    return {label: model.objects.count() for label, model in ROOT_MODELS.items()}


def _file_references() -> list[tuple[object, str]]:
    references: list[tuple[object, str]] = []
    for model, field_name in FILE_MODELS:
        field = model._meta.get_field(field_name)
        for file_name in (
            model.objects.exclude(**{field_name: ""})
            .values_list(field_name, flat=True)
        ):
            if file_name:
                references.append((field.storage, str(file_name)))
    return references


class Command(BaseCommand):
    help = (
        "Elimina datos operativos de prueba y reinicia la numeracion visible, "
        "conservando usuarios, permisos especificos, fotos y catalogos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Ejecuta la limpieza. Sin esta opcion solo se muestra una simulacion.",
        )
        parser.add_argument(
            "--keep-files",
            action="store_true",
            help="Conserva los archivos fisicos de evidencia (no recomendado).",
        )

    def handle(self, *args, **options):
        before_operational = _operational_counts()
        protected_before = _protected_counts()
        file_references = _file_references()

        self.stdout.write("Datos operativos encontrados:")
        for label, count in before_operational.items():
            self.stdout.write(f"  - {label}: {count}")
        self.stdout.write(
            f"  - archivos de evidencia referenciados: {len(file_references)}"
        )
        self.stdout.write(
            "Datos protegidos: "
            f"{protected_before['users']} usuarios, "
            f"{sum(protected_before['catalog'].values())} registros de catalogo."
        )

        if not options["confirm"]:
            self.stdout.write(
                self.style.WARNING(
                    "SIMULACION: no se modifico nada. Use --confirm despues de "
                    "realizar y verificar el backup."
                )
            )
            return

        with transaction.atomic():
            for model in ROOT_MODELS.values():
                model.objects.all().delete()

            protected_after = _protected_counts()
            if protected_after != protected_before:
                raise CommandError(
                    "La verificacion de seguridad detecto cambios en usuarios, "
                    "permisos o catalogos. La transaccion fue revertida."
                )

            remaining = _operational_counts()
            if any(remaining.values()):
                raise CommandError(
                    f"Quedaron datos operativos luego de la limpieza: {remaining}"
                )

        deleted_files = 0
        failed_files: list[str] = []
        if not options["keep_files"]:
            for storage, name in file_references:
                try:
                    if storage.exists(name):
                        storage.delete(name)
                        deleted_files += 1
                except OSError:
                    failed_files.append(name)

        self.stdout.write(self.style.SUCCESS("Limpieza operativa completada."))
        self.stdout.write(
            "Se conservaron sin cambios: "
            f"{protected_after['users']} usuarios, "
            f"{sum(protected_after['catalog'].values())} registros de catalogo."
        )
        self.stdout.write(
            "Numeracion reiniciada: la proxima anomalia y el proximo tratamiento "
            "comenzaran en 0001 para el ano actual."
        )
        if options["keep_files"]:
            self.stdout.write(
                self.style.WARNING(
                    "Los archivos fisicos de evidencia fueron conservados."
                )
            )
        else:
            self.stdout.write(f"Archivos fisicos eliminados: {deleted_files}")
        if failed_files:
            raise CommandError(
                "La base fue limpiada, pero no se pudieron eliminar estos archivos: "
                + ", ".join(failed_files)
            )
