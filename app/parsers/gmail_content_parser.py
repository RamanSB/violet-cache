"""
Gmail-specific parser implementation.
"""

import base64
from typing import Any, Dict, Optional, Tuple

from app.normalisers.email_normaliser import EmailNormaliser
from app.parsers.email_content_parser import EmailContentParser
from app.schema.schemas import ParsedEmailContent


class GmailContentParser(EmailContentParser):
    """
    TODO:
    a) Handle parsing attachments
    b) Handle parsing mime types together (currently only taking text over html)
    c) Understand the data returned in the API in detail to extract as much value as possible.
    D - Now: Create a Normalizer class / instance var that will ensure we
    only retain data from the current message and not the entire text appended email chain.
    """

    def __init__(self, normaliser: EmailNormaliser):
        self.normaliser = normaliser

    def parse(self, message: Dict[str, Any]) -> ParsedEmailContent:
        try:
            payload = message.get("payload", {})

            mime_type = payload.get("mimeType")

            text_plain, text_html = self._extract_bodies(payload)

            # headers = self._headers_to_dict(payload.get("headers", []))

            normalized_text = self.normaliser.normalise(
                text_plain=text_plain, text_html=text_html
            )

            return ParsedEmailContent(
                container_mime_type=mime_type,
                text_plain=text_plain,
                text_html=text_html,
                normalized_text=normalized_text,
                # headers=headers,
            )
        except Exception as ex:
            print(f"Unable to parse message id ({message['id']}): {ex}")
            return None

    def _extract_bodies(
        self, payload: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        text_plain = None
        text_html = None

        def walk(part: Dict[str, Any]):
            nonlocal text_plain, text_html

            mime_type = part.get("mimeType")
            body = part.get("body", {})
            data = body.get("data")

            if mime_type == "text/plain" and data and text_plain is None:
                decoded = self._decode_base64url(data)
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(decoded, "html.parser")
                # Heuristic: classify as HTML only if substantial part is HTML (not just presence of any tag)
                tag_count = len(soup.find_all())
                content_length = len(decoded.strip())
                tag_density = tag_count / content_length if content_length else 0
                contains_html_tag = any(
                    tag in decoded.lower()
                    for tag in ("<html", "<body", "<head", "<table", "<div")
                )

                # Criteria:
                # - Large tag density or HTML doc structure tags, and also not just a <br> or <a>
                if (tag_density > 0.01 and tag_count > 5) or contains_html_tag:
                    if text_html is None:
                        text_html = decoded
                else:
                    text_plain = decoded

            elif mime_type == "text/html" and data and text_html is None:
                text_html = self._decode_base64url(data)

            for child in part.get("parts", []) or []:
                walk(child)

        walk(payload)

        return text_plain, text_html

    def _decode_base64url(self, data: str) -> str:
        padded = data + "=" * (-len(data) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        return decoded_bytes.decode("utf-8", errors="replace")

    def _headers_to_dict(self, headers: list) -> Dict[str, str]:
        result = {}

        for h in headers:
            name = h.get("name")
            value = h.get("value")

            if name:
                result[name] = value

        return result
