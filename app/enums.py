from enum import Enum
import uuid


class EmailProvider(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobType(str, Enum):
    mailbox_sync = "mailbox_sync"


class ResourceType(str, Enum):
    email_account = "email_account"
    casefile = "casefile"
    document = "document"


HARDCODED_USER_ID = uuid.UUID("5aeaba4e-420c-4d98-b799-4c1c0a29aba6")
