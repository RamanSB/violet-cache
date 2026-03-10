import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup


@dataclass
class FooterBlockScore:
    index: int
    text: str
    score: float
    reasons: list[str]


class EmailNormaliser:
    ON_WROTE_RE = re.compile(r"\nOn .*?wrote:\s*", re.IGNORECASE | re.DOTALL)
    OUTLOOK_REPLY_RE = re.compile(
        r"from:\s*.*?sent:\s*.*?to:\s*.*?(?:cc:\s*.*?)*subject:\s*.*",
        re.IGNORECASE | re.DOTALL,
    )
    ORIGINAL_MESSAGE_RE = re.compile(
        r"-----Original Message-----.*",
        re.IGNORECASE | re.DOTALL,
    )

    STRONG_FOOTER_PATTERNS: list[tuple[re.Pattern, float, str]] = [
        (re.compile(r"\bprivacy (?:policy|notice|statement)\b", re.I), 4.0, "privacy"),
        (re.compile(r"\bunsubscribe\b", re.I), 4.0, "unsubscribe"),
        (
            re.compile(r"\bmanage (?:your )?preferences\b", re.I),
            4.0,
            "manage_preferences",
        ),
        (
            re.compile(r"\bprefer fewer emails\b", re.I),
            4.0,
            "prefer_fewer_emails",
        ),
        (
            re.compile(r"\bemail disclaimer\b", re.I),
            4.0,
            "email_disclaimer",
        ),
        (re.compile(r"\bconfidential\b", re.I), 3.0, "confidential"),
        (re.compile(r"\bprivileged\b", re.I), 3.0, "privileged"),
        (
            re.compile(r"\bintended recipient\b", re.I),
            3.0,
            "intended_recipient",
        ),
        (
            re.compile(r"\bif you are not the intended recipient\b", re.I),
            4.0,
            "wrong_recipient_warning",
        ),
        (
            re.compile(r"\bregistered office\b", re.I),
            3.0,
            "registered_office",
        ),
        (
            re.compile(r"\bregistered in england(?: and wales)?\b", re.I),
            3.0,
            "registered_in_england",
        ),
        (
            re.compile(r"\bauthori[sz]ed and regulated\b", re.I),
            3.5,
            "authorised_regulated",
        ),
        (
            re.compile(r"\bfinancial conduct authority\b|\bfca\b", re.I),
            4.0,
            "fca",
        ),
        (
            re.compile(r"\bgeneral data protection regulation\b|\bgdpr\b", re.I),
            4.0,
            "gdpr",
        ),
        (re.compile(r"\bdata protection\b", re.I), 2.5, "data_protection"),
        (re.compile(r"\bpersonal data\b", re.I), 2.0, "personal_data"),
        (
            re.compile(r"\ball rights reserved\b", re.I),
            3.0,
            "all_rights_reserved",
        ),
        (re.compile(r"\bcopyright\b", re.I), 2.5, "copyright"),
        (
            re.compile(r"\bunable to accept incoming emails\b", re.I),
            3.0,
            "no_incoming_emails",
        ),
        (re.compile(r"\bdo not reply\b", re.I), 3.0, "do_not_reply"),
        (re.compile(r"\bvirus free\b", re.I), 2.5, "virus_free"),
        (
            re.compile(r"\bdoes not accept liability\b", re.I),
            3.0,
            "liability",
        ),
        (
            re.compile(r"\bhow we use your information\b", re.I),
            3.5,
            "how_we_use_info",
        ),
        (
            re.compile(r"\bbeware of cyber-?crime\b", re.I),
            3.0,
            "cybercrime_warning",
        ),
        (
            re.compile(r"\bbanking details will not change\b", re.I),
            3.0,
            "banking_warning",
        ),
        (
            re.compile(r"\bnotify the sender immediately\b", re.I),
            3.0,
            "notify_sender",
        ),
        (re.compile(r"\bdestroy this email\b", re.I), 2.5, "destroy_email"),
        (
            re.compile(r"\bmonitor all email communications\b", re.I),
            3.0,
            "monitor_email_communications",
        ),
        (re.compile(r"\bmailing list\b", re.I), 2.5, "mailing_list"),
    ]

    SIGNATURE_PATTERNS: list[tuple[re.Pattern, float, str]] = [
        (re.compile(r"\bkind regards\b", re.I), -3.0, "kind_regards"),
        (re.compile(r"\bbest regards\b", re.I), -3.0, "best_regards"),
        (re.compile(r"\bregards\b", re.I), -1.0, "regards"),
        (re.compile(r"\bthanks\b", re.I), -2.0, "thanks"),
        (re.compile(r"\bthank you\b", re.I), -1.5, "thank_you"),
        (re.compile(r"\byours sincerely\b", re.I), -3.0, "yours_sincerely"),
        (re.compile(r"\byours faithfully\b", re.I), -3.0, "yours_faithfully"),
        (re.compile(r"\bcheers\b", re.I), -1.5, "cheers"),
        (re.compile(r"\bbranch manager\b", re.I), -2.0, "branch_manager"),
        (re.compile(r"\bresearcher\b", re.I), -1.5, "researcher"),
        (re.compile(r"\bdirector\b", re.I), -1.0, "director"),
        (re.compile(r"\bmanager\b", re.I), -0.5, "manager"),
        (re.compile(r"\bfounder\b", re.I), -1.0, "founder"),
        (re.compile(r"\bhead of\b", re.I), -1.0, "head_of"),
        (re.compile(r"\bmobile\b", re.I), -0.5, "mobile"),
        (re.compile(r"\btel\b", re.I), -0.5, "tel"),
        (re.compile(r"\bphone\b", re.I), -0.5, "phone"),
        (re.compile(r"\bemail\b", re.I), -0.5, "email_label"),
        (re.compile(r"\bwebsite\b", re.I), -0.5, "website_label"),
    ]

    URL_RE = re.compile(r"https?://|www\.", re.I)
    EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
    PHONE_RE = re.compile(r"(?:(?:\+\d{1,3}[\s\-]?)?(?:\(?0?\d+\)?[\s\-]?){6,})", re.I)
    VAT_RE = re.compile(r"\bvat(?:\s+number)?\b", re.I)
    COMPANY_NO_RE = re.compile(
        r"\b(?:company number|registered number|registered no\.?|reg\.?\s*no\.?)\s*[:#]?\s*\d{4,}\b",
        re.I,
    )
    FOOTER_HEADING_RE = re.compile(
        r"^(?:notice|email disclaimer|disclaimer)\s*:?\s*$", re.I
    )

    def normalise(self, *, text_plain: str | None, text_html: str | None) -> str | None:
        text = self._select_base_text(text_plain=text_plain, text_html=text_html)
        if not text:
            return None

        text = self._pre_normalise_for_parsing(text)
        text = self._strip_quoted_history(text)
        text = self._collapse_whitespace(text)
        text = self._strip_footer_boilerplate(text)
        text = self._collapse_whitespace(text)
        text = text.strip()
        return text or None

    def _pre_normalise_for_parsing(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u00a0", " ")
        text = text.replace("\u200b", "").replace("\ufeff", "")

        # remove mailto wrappers but keep visible email address
        text = re.sub(r"<mailto:([^>]+)>", "", text, flags=re.I)

        # collapse repeated spaces per line, but preserve line structure
        lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    # TODO: Revisit this logic (include regional scoring - consider neighboring blocks).
    def _strip_footer_boilerplate(self, text: str) -> str:
        blocks = self._split_blocks(text)
        if not blocks:
            return text

        scored_blocks = self._score_blocks(blocks)
        cut_index = self._detect_footer_boundary(scored_blocks)

        if cut_index is None:
            return self._cleanup_tail_lines(text)

        kept_blocks = blocks[:cut_index]
        cleaned = "\n\n".join(kept_blocks).strip()
        cleaned = self._cleanup_tail_lines(cleaned)

        # Safety: if we trimmed too aggressively, keep original
        if not cleaned or len(cleaned) < max(40, int(len(text) * 0.15)):
            return self._cleanup_tail_lines(text)

        return cleaned

    def _split_blocks(self, text: str) -> list[str]:
        raw_blocks = re.split(r"\n\s*\n", text)
        return [block.strip() for block in raw_blocks if block and block.strip()]

    def _score_blocks(self, blocks: list[str]) -> list[FooterBlockScore]:
        total_blocks = len(blocks)
        scored_blocks: list[FooterBlockScore] = []

        for index, block in enumerate(blocks):
            score = 0.0
            reasons: list[str] = []
            lower = block.lower()

            for pattern, weight, label in self.STRONG_FOOTER_PATTERNS:
                if pattern.search(block):
                    score += weight
                    reasons.append(f"{label} ({weight:+.1f})")

            for pattern, weight, label in self.SIGNATURE_PATTERNS:
                if pattern.search(block):
                    score += weight
                    reasons.append(f"{label} ({weight:+.1f})")

            url_count = len(self.URL_RE.findall(block))
            if url_count >= 3:
                score += 2.0
                reasons.append("3+ urls (+2.0)")
            elif url_count == 2:
                score += 1.5
                reasons.append("2 urls (+1.5)")
            elif url_count == 1:
                score += 0.5
                reasons.append("1 url (+0.5)")

            if self.VAT_RE.search(block):
                score += 2.0
                reasons.append("vat (+2.0)")

            if self.COMPANY_NO_RE.search(block):
                score += 2.0
                reasons.append("company_no (+2.0)")

            if "registered office" in lower:
                score += 1.5
                reasons.append("registered_office_bonus (+1.5)")

            if "registered in england" in lower:
                score += 1.5
                reasons.append("registered_in_england_bonus (+1.5)")

            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if lines and self.FOOTER_HEADING_RE.match(lines[0]):
                score += 2.5
                reasons.append("footer_heading (+2.5)")

            if len(block) > 450:
                score += 1.0
                reasons.append("long_block (+1.0)")

            if len(block) > 900:
                score += 1.0
                reasons.append("very_long_block (+1.0)")

            if total_blocks > 1:
                pos_ratio = index / (total_blocks - 1)
                if pos_ratio >= 0.75:
                    score += 1.0
                    reasons.append("near_bottom (+1.0)")
                if pos_ratio >= 0.90:
                    score += 1.0
                    reasons.append("very_near_bottom (+1.0)")

            if self._looks_like_contact_card(block):
                score -= 3.0
                reasons.append("contact_card (-3.0)")

            if self._looks_like_human_message(block):
                score -= 1.5
                reasons.append("human_message (-1.5)")

            scored_blocks.append(
                FooterBlockScore(
                    index=index,
                    text=block,
                    score=score,
                    reasons=reasons,
                )
            )

        return scored_blocks

    def _detect_footer_boundary(
        self, scored_blocks: list[FooterBlockScore]
    ) -> Optional[int]:
        if not scored_blocks:
            return None

        cut_index: Optional[int] = None
        in_footer_region = False
        suspicious_run = 0

        for i in range(len(scored_blocks) - 1, -1, -1):
            block = scored_blocks[i]

            if block.score >= 7.0:
                in_footer_region = True
                cut_index = i
                continue

            if block.score >= 4.0:
                suspicious_run += 1
                if in_footer_region or suspicious_run >= 2:
                    in_footer_region = True
                    cut_index = i
                continue

            if in_footer_region:
                break

            suspicious_run = 0

        if cut_index is None:
            return None

        if cut_index == 0:
            return None

        return cut_index

    def _looks_like_contact_card(self, block: str) -> bool:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or len(lines) > 10:
            return False

        legal_hits = 0
        for pattern, _, _ in self.STRONG_FOOTER_PATTERNS:
            if pattern.search(block):
                legal_hits += 1

        if legal_hits >= 2:
            return False

        short_lines = sum(1 for line in lines if len(line) <= 70)
        email_present = bool(self.EMAIL_RE.search(block))
        phone_present = bool(self.PHONE_RE.search(block))
        url_present = bool(self.URL_RE.search(block))
        title_present = bool(
            re.search(
                r"\b(manager|director|researcher|founder|recruiter|consultant|partner|associate|head)\b",
                block,
                re.I,
            )
        )

        score = 0
        if short_lines >= max(3, len(lines) - 1):
            score += 1
        if email_present:
            score += 1
        if phone_present:
            score += 1
        if url_present:
            score += 1
        if title_present:
            score += 1

        return score >= 2

    def _looks_like_human_message(self, block: str) -> bool:
        lower = block.lower()

        legal_terms = [
            "privacy policy",
            "privacy notice",
            "privacy statement",
            "unsubscribe",
            "registered office",
            "registered in england",
            "financial conduct authority",
            "gdpr",
            "confidential",
            "intended recipient",
        ]
        if any(term in lower for term in legal_terms):
            return False

        conversational_patterns = [
            r"\bare you free\b",
            r"\bplease find attached\b",
            r"\bthank you for\b",
            r"\bif you would like\b",
            r"\bplease do\b",
            r"\bplease ignore\b",
            r"\bgood luck\b",
            r"\bkind regards\b",
            r"\bthanks\b",
            r"\bhi\b",
            r"\bhello\b",
            r"\bdear\b",
        ]
        hits = sum(
            1 for pattern in conversational_patterns if re.search(pattern, lower, re.I)
        )
        sentence_like = len(re.findall(r"[.!?]", block)) >= 1
        return hits >= 1 and sentence_like

    def _cleanup_tail_lines(self, text: str) -> str:
        if not text:
            return text

        lines = text.splitlines()
        cleaned_lines = list(lines)

        trailing_line_patterns = [
            r"^\s*prefer fewer emails.*$",
            r"^\s*click here\s*$",
            r"^\s*unsubscribe\s*$",
            r"^\s*manage (?:your )?preferences\s*$",
            r"^\s*--\s*$",
            r"^\s*[-_=]{2,}\s*$",
        ]

        while cleaned_lines:
            tail = cleaned_lines[-1].strip()
            if not tail:
                cleaned_lines.pop()
                continue

            matched = False
            for pattern in trailing_line_patterns:
                if re.match(pattern, tail, flags=re.I):
                    cleaned_lines.pop()
                    matched = True
                    break

            if matched:
                continue

            break

        return "\n".join(cleaned_lines).strip()

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
        first_start = None

        for pattern in (
            self.ON_WROTE_RE,
            self.OUTLOOK_REPLY_RE,
            self.ORIGINAL_MESSAGE_RE,
        ):
            match = pattern.search(text)
            if match:
                if first_start is None or match.start() < first_start:
                    first_start = match.start()

        if first_start is not None:
            return text[:first_start]

        return text

    def _collapse_whitespace(self, text: str) -> str:
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text
