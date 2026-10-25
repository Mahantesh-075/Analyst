import io
import zipfile

import pytest

from app.core.errors import AppException
from app.services.sniffer import SnifferService


def test_rejects_macro_filename() -> None:
    sniffer = SnifferService()
    dummy = b"PK\x03\x04dummy content"
    with pytest.raises(AppException) as exc:
        sniffer.inspect_safety(dummy, "malicious.xlsm")
    assert "Macro-enabled" in exc.value.message
    assert exc.value.status_code == 400


def test_rejects_pe_executable() -> None:
    sniffer = SnifferService()
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
    with pytest.raises(AppException) as exc:
        sniffer.inspect_safety(fake_exe, "clean_data.csv")
    assert "Executable files are strictly forbidden" in exc.value.message


def test_rejects_elf_executable() -> None:
    sniffer = SnifferService()
    fake_elf = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    with pytest.raises(AppException) as exc:
        sniffer.inspect_safety(fake_elf, "records.csv")
    assert "Executable files are strictly forbidden" in exc.value.message


def test_rejects_archive_with_embedded_vba_macro() -> None:
    sniffer = SnifferService()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/vbaProject.bin", b"fake macro binary bytecode")
        z.writestr("xl/workbook.xml", b"<workbook/>")

    with pytest.raises(AppException) as exc:
        sniffer.inspect_safety(buf.getvalue(), "report.xlsx")
    assert "embedded VBA macros" in exc.value.message


def test_rejects_archive_with_embedded_executable() -> None:
    sniffer = SnifferService()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("payload.exe", b"binary content")
        z.writestr("data.csv", b"a,b,c\n1,2,3")

    with pytest.raises(AppException) as exc:
        sniffer.inspect_safety(buf.getvalue(), "data.zip")
    assert "Archive contains executable content" in exc.value.message


def test_accepts_clean_csv() -> None:
    sniffer = SnifferService()
    clean_csv = b"name,age,country\nAlice,30,Canada\nBob,25,USA"
    sniffer.inspect_safety(clean_csv, "people.csv")
    parsed = sniffer.sniff(clean_csv, "people.csv")
    assert parsed["delimiter"] == ","
    assert parsed["format"] == "csv"
