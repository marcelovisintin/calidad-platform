from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from apps.notifications.services.email_template_catalog import render_email_template


class Command(BaseCommand):
    help = "Envia un unico correo para validar la configuracion SMTP."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, dest="recipient")
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirma que se desea realizar un envio real.",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Debe agregar --confirm para realizar el correo de prueba.")

        recipient = options["recipient"].strip()
        try:
            validate_email(recipient)
        except ValidationError as exc:
            raise CommandError("La direccion de destino no es valida.") from exc

        if not settings.EMAIL_HOST_USER:
            raise CommandError("EMAIL_HOST_USER no esta configurado.")
        if not settings.EMAIL_HOST_PASSWORD:
            raise CommandError("EMAIL_HOST_PASSWORD no esta configurado.")

        default_subject = "Prueba de correo - Sistema de Gestión de Calidad"
        default_body = (
            "La configuración de correo del Sistema de Gestión de Calidad funciona correctamente.\n\n"
            "Este mensaje es únicamente una prueba controlada."
        )
        subject, body = render_email_template(
            code="smtp_configuration_test",
            fallback_subject=default_subject,
            fallback_body=default_body,
        )
        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        try:
            delivered = message.send(fail_silently=False)
        except Exception as exc:
            raise CommandError(f"Google Workspace rechazo el envio: {exc}") from exc
        if delivered != 1:
            raise CommandError("El backend SMTP no confirmo la entrega del correo de prueba.")

        self.stdout.write(self.style.SUCCESS(f"Correo de prueba enviado a {recipient}."))
