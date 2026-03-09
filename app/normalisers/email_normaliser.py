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

    STRONG_FOOTER_MARKERS = [
        "this email and any attachments may be confidential",
        "this message is confidential",
        "email disclaimer",
        "registered office",
        "registered in england",
        "for more information about how we manage your data",
        "we are unable to accept incoming emails to this address",
        "authorised in the united kingdom by the financial conduct authority",
        "if you are not the intended recipient",
    ]

    MEDIUM_FOOTER_MARKERS = [
        "privacy policy",
        "privacy notice",
        "privacy statement",
        "unsubscribe",
        "manage your preferences",
        "prefer fewer emails from me?",
        "all rights reserved",
        "vat number",
    ]

    WEAK_FOOTER_MARKERS = [
        "copyright",
        "company number",
        "registered address",
    ]

    # TODO: Revisit this logic
    def _strip_footer_boilerplate(self, text: str) -> str:
        if not text.strip():
            return text

        lower = text.lower()

        # Only inspect bottom half-ish of the email
        start_idx = int(len(lower) * 0.5)
        tail = lower[start_idx:]

        matches: list[tuple[int, int]] = []  # (absolute_position, score)

        for marker in self.STRONG_FOOTER_MARKERS:
            rel = tail.find(marker)
            if rel != -1:
                matches.append((start_idx + rel, 3))

        for marker in self.MEDIUM_FOOTER_MARKERS:
            rel = tail.find(marker)
            if rel != -1:
                matches.append((start_idx + rel, 2))

        for marker in self.WEAK_FOOTER_MARKERS:
            rel = tail.find(marker)
            if rel != -1:
                matches.append((start_idx + rel, 1))

        if not matches:
            return text

        matches.sort(key=lambda x: x[0])

        # If earliest match is strong, cut there
        first_pos, first_score = matches[0]
        if first_score >= 3:
            return text[:first_pos].rstrip()

        # Otherwise require enough nearby evidence
        window_start = first_pos
        window_end = first_pos + 500
        score_sum = sum(
            score for pos, score in matches if window_start <= pos <= window_end
        )

        if score_sum >= 4:
            return text[:first_pos].rstrip()

        return text

    def _collapse_whitespace(self, text: str) -> str:
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text

    def normalise(self, *, text_plain: str | None, text_html: str | None) -> str | None:
        text = self._select_base_text(text_plain=text_plain, text_html=text_html)
        if not text:
            return None

        text = self._strip_quoted_history(text)
        text = self._collapse_whitespace(text)
        text = self._strip_footer_boilerplate(text)
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
