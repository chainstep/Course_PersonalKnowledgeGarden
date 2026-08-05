from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_garden.ingestion import IngestionService
from knowledge_garden.models import (
    DecodeError,
    EncryptedPDFError,
    OCRNotSupportedError,
    UnsupportedTypeError,
)


def test_encrypted_pdf_rejected(tmp_path: Path, settings, repository):
    import pymupdf

    sample = tmp_path / "secret.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret")
    doc.save(sample)
    doc.close()
    reloaded = pymupdf.open(sample)
    encrypted_path = tmp_path / "encrypted.pdf"
    reloaded.save(
        str(encrypted_path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="secret",
        owner_pw="owner",
    )
    reloaded.close()
    with pytest.raises((EncryptedPDFError, UnsupportedTypeError, ValueError)):
        IngestionService(repository, settings).add(str(encrypted_path))


def test_image_only_pdf_rejected(tmp_path: Path, settings, repository):
    import pymupdf

    sample = tmp_path / "image.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 0)
    pixmap.set_pixel(0, 0, (255, 0, 0))
    page.insert_image(pymupdf.Rect(0, 0, 50, 50), pixmap=pixmap)
    doc.save(sample)
    doc.close()
    with pytest.raises((OCRNotSupportedError, UnsupportedTypeError)):
        IngestionService(repository, settings).add(str(sample))


def test_unsupported_extension_rejected(tmp_path: Path, settings, repository):
    sample = tmp_path / "binary.bin"
    sample.write_bytes(b"\x00\x01")
    with pytest.raises(UnsupportedTypeError):
        IngestionService(repository, settings).add(str(sample))


def test_non_utf8_rejected(tmp_path: Path, settings, repository):
    sample = tmp_path / "note.md"
    sample.write_bytes(b"# Heading\n\n\xc3\x28invalid")
    with pytest.raises((DecodeError, UnsupportedTypeError, UnicodeDecodeError)):
        IngestionService(repository, settings).add(str(sample))
