from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="marcelo.v@schneider.ar",
    EMAIL_HOST_PASSWORD="test-app-password",
    DEFAULT_FROM_EMAIL="marcelo.v@schneider.ar",
)
class TestEmailConfigurationCommandTests(SimpleTestCase):
    def test_confirmation_is_required(self):
        with self.assertRaises(CommandError):
            call_command("test_email_configuration", recipient="marcelo.v@schneider.ar")

    def test_sends_single_controlled_email(self):
        stdout = StringIO()

        call_command(
            "test_email_configuration",
            recipient="marcelo.v@schneider.ar",
            confirm=True,
            stdout=stdout,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["marcelo.v@schneider.ar"])
        self.assertIn("Correo de prueba enviado", stdout.getvalue())
