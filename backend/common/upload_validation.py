from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from rest_framework import serializers


ALLOWED_EVIDENCE_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "application/rtf",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/zip",
    "application/x-zip-compressed",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
    "image/heic",
    "image/heif",
}

ALLOWED_EVIDENCE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".txt",
    ".csv",
    ".rtf",
    ".odt",
    ".ods",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}

ALLOWED_PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
GENERIC_BINARY_CONTENT_TYPES = {"", "application/octet-stream"}


def _validate_uploaded_file(
    file_obj,
    *,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
    max_size: int,
    format_error: str,
):
    file_name = (getattr(file_obj, "name", "") or "").strip()
    extension = Path(file_name).suffix.lower()
    content_type = (
        (getattr(file_obj, "content_type", "") or "").split(";", 1)[0].strip().lower()
    )
    file_size = getattr(file_obj, "size", 0) or 0

    if extension not in allowed_extensions:
        raise serializers.ValidationError(format_error)

    if (
        content_type not in allowed_content_types
        and content_type not in GENERIC_BINARY_CONTENT_TYPES
    ):
        raise serializers.ValidationError(
            "El tipo de contenido del archivo no coincide con un formato permitido."
        )

    if file_size > max_size:
        max_megabytes = max_size / (1024 * 1024)
        raise serializers.ValidationError(
            f"El archivo supera el maximo permitido de {max_megabytes:g} MB."
        )

    return file_obj


def validate_evidence_file(file_obj):
    return _validate_uploaded_file(
        file_obj,
        allowed_extensions=ALLOWED_EVIDENCE_EXTENSIONS,
        allowed_content_types=ALLOWED_EVIDENCE_CONTENT_TYPES,
        max_size=settings.EVIDENCE_FILE_MAX_SIZE,
        format_error="Solo se permiten evidencias en formato imagen, PDF, Word, Excel, texto o ZIP.",
    )


def validate_user_photo(file_obj):
    return _validate_uploaded_file(
        file_obj,
        allowed_extensions=ALLOWED_PHOTO_EXTENSIONS,
        allowed_content_types=ALLOWED_PHOTO_CONTENT_TYPES,
        max_size=settings.USER_PHOTO_MAX_SIZE,
        format_error="La foto debe estar en formato JPG, PNG o WEBP.",
    )


def normalized_upload_content_type(file_obj) -> str:
    content_type = (
        (getattr(file_obj, "content_type", "") or "").split(";", 1)[0].strip().lower()
    )
    if content_type not in GENERIC_BINARY_CONTENT_TYPES:
        return content_type
    guessed_type, _ = mimetypes.guess_type(getattr(file_obj, "name", "") or "")
    return guessed_type or "application/octet-stream"
