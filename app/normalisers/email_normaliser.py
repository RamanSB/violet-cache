import re
from typing import Optional

from bs4 import BeautifulSoup


class EmailNormaliser:
    ON_WROTE_RE = re.compile(r"\nOn .*?wrote:\s*", re.IGNORECASE | re.DOTALL)
    OUTLOOK_REPLY_RE = re.compile(
        r"from:\s*.*?sent:\s*.*?to:\s*.*?subject:\s*.*",
        re.IGNORECASE | re.DOTALL,
    )
    ORIGINAL_MESSAGE_RE = re.compile(
        r"-----Original Message-----.*",
        re.IGNORECASE | re.DOTALL,
    )

    def normalise(self, *, text_plain: str | None, text_html: str | None) -> str | None:
        text = self._select_base_text(text_plain=text_plain, text_html=text_html)
        if not text:
            return None

        text = self._strip_quoted_history(text)
        text = self._collapse_whitespace(text)

        text = text.strip()
        return text or None

    def _select_base_text(
        self, *, text_plain: str | None, text_html: str | None
    ) -> str | None:
        if text_plain and text_plain.strip():
            return text_plain

        if text_html and text_html.strip():
            soup = BeautifulSoup(text_html, "html.parser")
            return soup.get_text("\n", strip=True)

        return None

    def _strip_quoted_history(self, text: str) -> str:
        for pattern in (
            self.ON_WROTE_RE,
            self.OUTLOOK_REPLY_RE,
            self.ORIGINAL_MESSAGE_RE,
        ):
            match = pattern.search(text)
            if match:
                return text[: match.start()]
        return text

    def _collapse_whitespace(self, text: str) -> str:
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text
