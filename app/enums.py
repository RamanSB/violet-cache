from enum import Enum
import uuid


class EmailProvider(str, Enum):
    GMAIL = "GMAIL"
    OUTLOOK = "OUTLOOK"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class JobType(str, Enum):
    MAILBOX_SYNC = "MAILBOX_SYNC"


class JobPhase(str, Enum):
    METADATA_DISCOVERY = "METADATA_DISCOVERY"
    THREAD_EXPANSION = "THREAD_EXPANSION"
    CONTENT_FETCH = "CONTENT_FETCH"
    EMBEDDING = "EMBEDDING"
    COMPLETE = "COMPLETE"


class ResourceType(str, Enum):
    EMAIL_ACCOUNT = "EMAIL_ACCOUNT"
    CASEFILE = "CASEFILE"
    DOCUMENT = "DOCUMENT"


# TODO: Read in from JWT
HARDCODED_USER_ID = uuid.UUID("542d0824-a066-4670-8a81-811f848b4554")
