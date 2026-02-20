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


# TODO: Read in from JWT
HARDCODED_USER_ID = uuid.UUID("542d0824-a066-4670-8a81-811f848b4554")
