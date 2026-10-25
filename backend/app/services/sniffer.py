import io
import re
import zipfile
from typing import Any

import magic
import structlog

from app.core.errors import AppException, ErrorCode

logger = structlog.get_logger("service.sniffer")

# Maximum compression ratio allowed for archives (Zip Bomb protection)
MAX_ZIP_RATIO = 100
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB


class SnifferService:
    def inspect_safety(self, file_bytes: bytes, filename: str) -> None:
        """Content-based hostile file inspection.

        Rejects executables, macros (.xlsm), zip bombs, polyglots, and forbidden formats.
        """
        if not file_bytes:
            raise AppException(
                code=ErrorCode.VALIDATION_FAILED,
                message="Uploaded file is empty",
                status_code=400,
            )

        lower_name = filename.lower()
        if lower_name.endswith((".xlsm", ".xltm", ".xlam")):
            raise AppException(
                code=ErrorCode.SECURITY_VIOLATION,
                message="Macro-enabled spreadsheets (.xlsm/.xltm/.xlam) are strictly forbidden",
                status_code=400,
            )

        # Check PE / ELF header magic bytes
        if file_bytes.startswith(b"MZ") or file_bytes.startswith(b"\x7fELF"):
            raise AppException(
                code=ErrorCode.SECURITY_VIOLATION,
                message="Executable files are strictly forbidden",
                status_code=400,
            )

        # Check magic MIME type via libmagic
        try:
            mime = magic.from_buffer(file_bytes[:4096], mime=True)
            if mime in [
                "application/x-dosexec",
                "application/x-executable",
                "application/x-sharedlib",
                "application/x-pie-executable",
                "application/x-mach-binary",
                "application/x-msdos-program",
            ]:
                raise AppException(
                    code=ErrorCode.SECURITY_VIOLATION,
                    message=f"Executable binary detected ({mime})",
                    status_code=400,
                )
        except AppException:
            raise
        except Exception as e:
            logger.warning("magic_inspection_error", error=str(e))

        # Check ZIP / OOXML content (Excel .xlsx, zip archives)
        if file_bytes.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                    total_uncompressed = 0
                    total_compressed = 0

                    for info in z.infolist():
                        total_uncompressed += info.file_size
                        total_compressed += info.compress_size
                        member_name = info.filename.lower()

                        # Check for embedded macros
                        if "vba" in member_name or member_name.endswith((".bin", ".vba")):
                            if "vbaproject" in member_name:
                                raise AppException(
                                    code=ErrorCode.SECURITY_VIOLATION,
                                    message="Spreadsheet contains embedded VBA macros (vbaProject.bin)",
                                    status_code=400,
                                )

                        # Check for embedded executables or scripts
                        if member_name.endswith((
                            ".exe", ".dll", ".so", ".sh", ".bat", ".cmd", ".vbs", ".ps1"
                        )):
                            raise AppException(
                                code=ErrorCode.SECURITY_VIOLATION,
                                message=f"Archive contains executable content: {info.filename}",
                                status_code=400,
                            )

                    # Zip bomb protection
                    if total_compressed > 0:
                        ratio = total_uncompressed / total_compressed
                        if ratio > MAX_ZIP_RATIO:
                            raise AppException(
                                code=ErrorCode.SECURITY_VIOLATION,
                                message="Excessive compression ratio detected (potential zip bomb)",
                                status_code=400,
                            )
                    if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                        raise AppException(
                            code=ErrorCode.DATASET_TOO_LARGE,
                            message="Uncompressed content exceeds safety threshold",
                            status_code=413,
                        )
            except zipfile.BadZipFile as e:
                raise AppException(
                    code=ErrorCode.VALIDATION_FAILED,
                    message="Corrupted or invalid zip container",
                    status_code=400,
                ) from e

    def detect_encoding(self, file_bytes: bytes) -> str:
        """Sniff text encoding from sample bytes."""
        sample = file_bytes[:65536]
        # Check UTF-8 BOM
        if sample.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        # Try pure UTF-8
        try:
            sample.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass
        # Try windows-1252 / latin-1
        try:
            sample.decode("windows-1252")
            return "windows-1252"
        except UnicodeDecodeError:
            return "latin-1"

    def detect_delimiter(self, text_sample: str) -> str:
        """Count candidate delimiter occurrences across lines."""
        lines = [line for line in text_sample.splitlines() if line.strip()][:20]
        if not lines:
            return ","

        candidates = [",", "\t", ";", "|"]
        scores: dict[str, float] = {}

        for delim in candidates:
            counts = [line.count(delim) for line in lines]
            if not counts or counts[0] == 0:
                scores[delim] = 0.0
                continue
            # Variance in count across lines
            mean_c = sum(counts) / len(counts)
            if mean_c < 1.0:
                scores[delim] = 0.0
                continue
            variance = sum((c - mean_c) ** 2 for c in counts) / len(counts)
            # Higher score for consistent count per line
            scores[delim] = mean_c / (1.0 + variance)

        best_delim = max(scores, key=scores.get)  # type: ignore[arg-type]
        return best_delim if scores[best_delim] > 0 else ","

    def sniff(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        """Perform full inspection and return detected parse settings."""
        self.inspect_safety(file_bytes, filename)

        lower_name = filename.lower()
        if lower_name.endswith((".xlsx", ".xls")):
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
            sheets = wb.sheetnames
            wb.close()
            return {
                "format": "xlsx",
                "sheets": sheets,
                "sheet": sheets[0] if sheets else None,
                "header_row": 0,
            }
        elif lower_name.endswith(".parquet"):
            return {
                "format": "parquet",
            }
        else:
            # CSV or text tabular
            encoding = self.detect_encoding(file_bytes)
            sample_text = file_bytes[:32768].decode(encoding, errors="replace")
            delimiter = self.detect_delimiter(sample_text)

            # Detect decimal format from numeric patterns
            has_comma_decimal = bool(re.search(r"\b\d+,\d{2}\b", sample_text))
            decimal = "," if (has_comma_decimal and delimiter != ",") else "."
            thousands = "." if decimal == "," else ","

            return {
                "format": "tsv" if delimiter == "\t" else "csv",
                "encoding": encoding,
                "delimiter": delimiter,
                "header_row": 0,
                "decimal": decimal,
                "thousands": thousands,
            }
