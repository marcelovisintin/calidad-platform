from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from apps.actions.api.serializers import ActionEvidenceWriteSerializer
from apps.actions.api.treatment_serializers import (
    TreatmentEvidenceWriteSerializer,
    TreatmentTaskEvidenceWriteSerializer,
)


class UploadValidationTests(SimpleTestCase):
    def _serializer_is_valid(self, serializer_class, uploaded_file):
        serializer = serializer_class(data={"file": uploaded_file})
        return serializer.is_valid(), serializer.errors

    def test_all_evidence_serializers_reject_executable_extension(self):
        for serializer_class in (
            ActionEvidenceWriteSerializer,
            TreatmentEvidenceWriteSerializer,
            TreatmentTaskEvidenceWriteSerializer,
        ):
            uploaded_file = SimpleUploadedFile(
                "malware.exe",
                b"not-an-image",
                content_type="image/jpeg",
            )
            is_valid, errors = self._serializer_is_valid(serializer_class, uploaded_file)
            self.assertFalse(is_valid)
            self.assertIn("file", errors)

    def test_evidence_rejects_mime_type_that_does_not_match_allowed_formats(self):
        uploaded_file = SimpleUploadedFile(
            "evidence.jpg",
            b"not-an-image",
            content_type="application/x-msdownload",
        )

        is_valid, errors = self._serializer_is_valid(ActionEvidenceWriteSerializer, uploaded_file)

        self.assertFalse(is_valid)
        self.assertIn("file", errors)

    @override_settings(EVIDENCE_FILE_MAX_SIZE=3)
    def test_evidence_rejects_files_above_configured_size(self):
        uploaded_file = SimpleUploadedFile("evidence.txt", b"four", content_type="text/plain")

        is_valid, errors = self._serializer_is_valid(ActionEvidenceWriteSerializer, uploaded_file)

        self.assertFalse(is_valid)
        self.assertIn("file", errors)

    def test_evidence_accepts_allowed_extension_and_mime_type(self):
        uploaded_file = SimpleUploadedFile("evidence.txt", b"ok", content_type="text/plain")

        is_valid, errors = self._serializer_is_valid(ActionEvidenceWriteSerializer, uploaded_file)

        self.assertTrue(is_valid, errors)
