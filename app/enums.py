from enum import Enum


class EmailProvider(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
