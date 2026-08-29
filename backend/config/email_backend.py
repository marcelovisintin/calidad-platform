import ssl
from functools import cached_property

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend


class SmtpEmailBackend(EmailBackend):
    """SMTP backend that can trust an extra CA without changing global TLS."""

    @cached_property
    def ssl_context(self):
        context = ssl.create_default_context()
        ca_cert_file = getattr(settings, "EMAIL_CA_CERT_FILE", "")
        if ca_cert_file:
            context.load_verify_locations(cafile=ca_cert_file)
            # Some local antivirus TLS-inspection roots (including Avast) omit
            # the RFC 5280 "critical" marker on Basic Constraints. Python 3.14
            # rejects those only in strict mode. Keep certificate and hostname
            # verification enabled, relaxing strict parsing for this SMTP-only
            # context.
            context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        if self.ssl_certfile or self.ssl_keyfile:
            context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
        return context
