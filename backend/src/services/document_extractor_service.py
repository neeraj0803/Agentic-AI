from pathlib import Path
from docx import Document
from pypdf import PdfReader
import mammoth


class DocumentExtractorService:

    @staticmethod
    def extract_text(file_path: str) -> str:

        extension = Path(file_path).suffix.lower()

        if extension == ".txt":
            return DocumentExtractorService._extract_txt(
                file_path
            )

        elif extension == ".md":
            return DocumentExtractorService._extract_md(
                file_path
            )

        elif extension == ".docx":
            return DocumentExtractorService._extract_docx(
                file_path
            )

        elif extension == ".doc":
            return DocumentExtractorService._extract_doc(
                file_path
            )

        elif extension == ".pdf":
            return DocumentExtractorService._extract_pdf(
                file_path
            )

        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    @staticmethod
    def _extract_txt(file_path: str):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    @staticmethod
    def _extract_md(file_path: str):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    @staticmethod
    def _extract_docx(file_path: str):

        doc = Document(file_path)

        return "\n".join(
            paragraph.text
            for paragraph in doc.paragraphs
        )

    @staticmethod
    def _extract_pdf(file_path: str):

        reader = PdfReader(file_path)

        text = ""

        for page in reader.pages:
            text += page.extract_text() + "\n"

        return text

    @staticmethod
    def _extract_doc(file_path: str):

        with open(file_path, "rb") as file:

            result = mammoth.extract_raw_text(
                file
            )

            return result.value