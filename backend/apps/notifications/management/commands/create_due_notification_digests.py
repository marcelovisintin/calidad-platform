from django.conf import settings
from django.core.management.base import BaseCommand

from apps.notifications.services.digest_service import create_due_notification_digests


class Command(BaseCommand):
    help = "Genera un resumen diario de pendientes vencidos y proximos a vencer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=settings.EMAIL_DUE_REMINDER_DAYS,
            help="Cantidad de dias futuros incluidos en el resumen.",
        )

    def handle(self, *args, **options):
        result = create_due_notification_digests(reminder_days=options["days"])
        if not result["enabled"]:
            self.stdout.write(self.style.WARNING("Envio de correos desactivado por configuracion."))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Resumenes creados: {result['created']}; "
                f"usuarios evaluados: {result['users']}; "
                f"pendientes incluidos: {result['tasks']}."
            )
        )
