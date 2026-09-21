from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    file_name: str
    file_type: str
    extracted_text: str
