from typing import Dict, List
from email.utils import parsedate, parsedate_to_datetime
import uuid
from app.models.models import Email
from app.repositories.email_content_repository import EmailContentRepository
from app.repositories.email_repository import EmailRepository
from app.schema.schemas import ParsedEmailContent


def _convert_gmail_msg_to_email(gmail_message) -> Email:
    user_id = gmail_message["user_id"]
    email_account_id = gmail_message["email_account_id"]

    external_id = gmail_message["id"]
    thread_id = gmail_message["threadId"]
    size = gmail_message["sizeEstimate"]
    snippet = gmail_message["snippet"]
    payload_headers = gmail_message["payload"]["headers"]

    header_map = {}
    for obj in payload_headers:
        name = obj.get("name")
        if name in ["From", "from", "To", "Subject", "Date", "Cc"]:
            header_map[name] = obj.get("value")

    sender = header_map.get("From") or header_map.get(
        "from"
    )  # Gmail ~uses lowercase (see error_item-1.json)
    receiver = header_map.get("To")
    subject = header_map.get("Subject")
    cc = header_map.get("Cc")
    date_received = parsedate_to_datetime(header_map.get("Date"))

    # Basic mapping; fill in None/defaults for required Email fields not available
    # Some fields like user_id, email_account_id, cc might need to be set by the caller or omitted
    return Email(
        external_id=external_id,
        thread_id=thread_id,
        email_account_id=email_account_id,
        user_id=user_id,
        snippet=snippet,
        sender=sender,
        receiver=receiver,
        cc=cc,
        subject=subject,
        date_received=date_received,
        size=size,
    )


class EmailIngestionService:

    def __init__(
        self,
        email_repository: EmailRepository,
        email_content_repository: EmailContentRepository = None,
    ):
        self.email_repo = email_repository
        self.email_content_repo = email_content_repository

    def batch_upsert_email_metadata(self, *, data: List[Dict]):
        try:
            rows = [_convert_gmail_msg_to_email(obj).model_dump() for obj in data]
            self.email_repo.batch_upsert_metadata(rows=rows)
        except Exception as ex:
            print(f"Exception in batch_upsert_email_metadata: {ex}")
            raise ex

    def batch_upsert_email_content(self, *, data: List[ParsedEmailContent]):
        try:
            rows = [obj.model_dump() for obj in data]
            self.email_content_repo.batch_upsert_email_content(rows=rows)
        except Exception as ex:
            print(f"Exception in batch_upsert_email_content: {ex}")
            raise ex
