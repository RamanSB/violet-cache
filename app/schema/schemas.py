import uuid
from pydantic import BaseModel


# Use EmailContent in models instead of this, turn this in to a DTO.
class ParsedEmailContent(BaseModel):
    email_id: uuid.UUID | None = None
    container_mime_type: str | None = None
    text_plain: str | None = None
    text_html: str | None = None
    normalized_text: str | None = None
    # headers: dict[str, str] = {}
    # body_mime_types: list[str] = []
    # has_attachments: bool = False
