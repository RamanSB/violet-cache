"""
Gmail-specific parser implementation.
"""

import base64
from typing import Any, Dict, Optional, Tuple

from app.parsers.email_content_parser import EmailContentParser
from app.schema.schemas import ParsedEmailContent


class GmailContentParser(EmailContentParser):

    def parse(self, message: Dict[str, Any]) -> ParsedEmailContent:
        payload = message.get("payload", {})

        mime_type = payload.get("mimeType")

        text_plain, text_html = self._extract_bodies(payload)

        headers = self._headers_to_dict(payload.get("headers", []))

        normalized_text = self._normalize_text(text_plain, text_html)

        return None
        # return ParsedEmailContent(
        #     mime_type=mime_type,
        #     text_plain=text_plain,
        #     text_html=text_html,
        #     normalized_text=normalized_text,
        #     headers=headers,
        # )

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
                text_plain = self._decode_base64url(data)

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

    def _normalize_text(
        self, text_plain: Optional[str], text_html: Optional[str]
    ) -> Optional[str]:
        """
        Produce embedding/search friendly text.
        """
        if text_plain and text_plain.strip():
            return text_plain.strip()

        if text_html:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text_html, "html.parser")
            return soup.get_text("\n", strip=True)

        return None
