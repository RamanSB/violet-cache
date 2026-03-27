import asyncio
import json
import random
from typing import Any, Dict, List, Tuple
import uuid


import httpx
from aiolimiter import AsyncLimiter
from sqlalchemy import Result
from sqlmodel import Session, col, func, select

from app.client.gmail import GmailClient
from app.client.openai import OpenAIClient
from app.db import engine
from app.dependencies import get_chunk_preparation_service, get_open_ai_client
from app.enums import HARDCODED_USER_ID
from app.models.models import Email, EmailContent
from app.normalisers.email_normaliser import EmailNormaliser
from app.parsers.gmail_content_parser import GmailContentParser
from app.repositories.email_account import EmailAccountRepository
from app.repositories.email_chunk import EmailChunkRepository
from app.repositories.email_content_repository import EmailContentRepository
from app.repositories.email_repository import EmailRepository
from app.repositories.google_auth import GoogleAuthDataRepository
from app.services import chunk_preparation_service
from app.services.email_ingestion.email_chunk_service import EmailChunkService
from app.services.embedding.embedding import EmbeddingService
from app.strategies.chunking.paragraph import ParagraphChunkifier
from app.tasks.celery.tasks import (
    expand_emails_per_thread,
    fetch_email_content,
    _prepare_email_chunks,
)

BASE_URL = "https://gmail.googleapis.com/gmail/v1"
OAUTH_ACCESS_TOKEN = ""
MY_GOOGLE_USER_ID = ""

HEADERS = {
    "Authorization": f"Bearer {OAUTH_ACCESS_TOKEN}",
    "Accept": "application/json",
}

RETRYABLE_STATUS = {403, 429, 500, 502, 503, 504}


async def get_with_backoff(
    client: httpx.AsyncClient, url: str, *, max_retries: int = 8
) -> httpx.Response:
    """
    Retries on Gmail rate limits / transient errors with exponential backoff + jitter.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            r = await client.get(url, headers=HEADERS)
            if r.status_code < 400:
                return r

            # Gmail often returns 403 for rate-limit exceeded (rateLimitExceeded)
            if r.status_code in RETRYABLE_STATUS:
                delay = min(60.0, (2**attempt) * 0.5) + random.random() * 0.25
                await asyncio.sleep(delay)
                continue

            r.raise_for_status()

        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exc = e
            delay = min(60.0, (2**attempt) * 0.5) + random.random() * 0.25
            await asyncio.sleep(delay)

    if last_exc:
        raise last_exc
    raise RuntimeError("Retries exhausted")


async def fetch_message_content(
    client: httpx.AsyncClient,
    user_id: str,
    msg_id: str,
) -> Dict[str, Any]:
    # Pull less data if you don’t need full payload:
    # format=metadata is usually enough, adjust as needed.
    url = f"{BASE_URL}/users/{user_id}/messages/{msg_id}?format=full"
    r = await get_with_backoff(client, url)
    return r.json()


# async def fetch_message_content(
#     client: httpx.AsyncClient,
#     user_id: str,
#     thread_id: str,
# ) -> Dict[str, Any]:
#     # Pull less data if you don’t need full payload:
#     # format=metadata is usually enough, adjust as needed.
#     url = f"{BASE_URL}/users/{user_id}/threads/{thread_id}?format=metadata"
#     r = await get_with_backoff(client, url)
#     return r.json()


async def fetch_messages_by_ids(
    message_ids: List[str],
    *,
    user_id: str = MY_GOOGLE_USER_ID,
    concurrency: int = 20,  # max in-flight requests
    rps: int = 50,  # max requests per second (tune)
) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(concurrency)
    limiter = AsyncLimiter(rps, time_period=1)  # rps per 1 second window

    async with httpx.AsyncClient(timeout=30.0) as client:

        async def one(mid: str) -> Dict[str, Any]:
            async with sem:
                async with limiter:
                    return await fetch_message_content(client, user_id, mid)

        # gather schedules all coroutines; limiter+sem prevents flooding
        coros = [one(mid) for mid in message_ids]
        return await asyncio.gather(*coros)


async def test_email_fetch():

    with Session(engine) as session:
        google_auth_repo = GoogleAuthDataRepository(session)
        google_auth_data = google_auth_repo.find_by_user_id(HARDCODED_USER_ID)
        headers = {
            "Authorization": f"Bearer {google_auth_data.access_token}",
            "Content-Type": "application/json",
        }
        gmail_client = GmailClient()

        try:
            message_ids = await gmail_client.list_messages(
                google_user_id=google_auth_data.google_user_id,
                headers=headers,
                include_spam_trash=False,
            )

            sample_msg_ids = message_ids  # [:200]

            email_messages = await gmail_client.fetch_messages_by_ids(
                message_ids=sample_msg_ids,
                headers=headers,
                google_user_id=google_auth_data.google_user_id,
            )

            with open(
                "/Users/raman/Documents/Development/Projects/notes-lab/app/data/json/all_emails_full_format.json",
                "w",
            ) as file:
                json.dump(email_messages, file)

        finally:
            await gmail_client.close()


async def test_fetch_messages_by_thread():
    with Session(engine) as session:
        google_auth_repo = GoogleAuthDataRepository(session)
        google_auth_data = google_auth_repo.find_by_user_id(HARDCODED_USER_ID)
        headers = {
            "Authorization": f"Bearer {google_auth_data.access_token}",
            "Content-Type": "application/json",
        }
        gmail_client = GmailClient()

        stmt = (
            select(Email.thread_id)
            .where(Email.user_id == HARDCODED_USER_ID)
            .group_by(Email.thread_id)
            .having(func.count() > 1)
            .order_by(func.count().desc())
        )
        thread_ids = session.exec(stmt).all()
        print(len(thread_ids))
        print(len(set(thread_ids)))

        try:
            msgs = await gmail_client.fetch_messages_by_thread_ids(
                thread_ids,
                google_user_id=google_auth_data.google_user_id,
                headers=headers,
                format="metadata",
            )

        except Exception as ex:
            print(f"Error while fetching message by thread: {ex}")
        finally:
            await gmail_client.close()


async def test_chunking_preparation_service():
    with Session(engine) as session:
        email_account_repo = EmailAccountRepository(session)
        email_repo = EmailRepository(session)
        email_content_repo = EmailContentRepository(session)
        chunk_prep_service = get_chunk_preparation_service(
            email_account_repo, email_repo, email_content_repo
        )

        chunk_prep_service.prepare_chunks_for_email_account(
            email="ramansb100@gmail.com"
        )


def test_chunking_algorithm():
    text = """
    Hey Ramandeep,

    Great chatting with you earlier. I appreciate you taking the time.

    Below is a list of companies worth sending your CV to. I've included a bit
    about them, followed by the headlines of each role including location,
    salary, hybrid vs on-site etc.

    *Zalos <https://www.zalos.ai/>*: builds Computer Agents that automate
    repetitive Finance workflows like categorization & reconciliation, without
    changing Finance systems. Under the hood, they use AI agents that log into
    existing ERPs and finance tools, interact with real UIs, and execute tasks
    like a human operator - while maintaining full auditability and control for
    finance teams.

    - Founding Product Engineer
    - TypeScript, React, Next.js, Python, FastAPI, Node, AWS/GCP
    - £90,000-£140,000 + equity
    - Victoria, London (hybrid)
    - Pre-seed $3.5M

    *Cosine <https://cosine.sh/>*: builds research-driven AI systems like Genie
    that can autonomously reason about and modify large codebases, combining
    in-house model post-training, evaluation frameworks and agent orchestration
    to create reliable AI engineers for complex enterprise environments.

    - Product Engineer
    - TypeScript, React, Next.js, Node, Python, Go, AWS
    - £80,000-£120,000 + equity
    - Hoxton, London (5 days on-site)
    - Series A $TBC

    *Heron Data <https://www.herondata.io/>*: builds AI systems that
    automatically extract, structure and verify data from complex financial
    documents, enabling lenders and fintechs to automate underwriting and
    operational workflows with reliable, production-grade LLM pipelines.

    - Full Stack Engineer
    - Python, FastAPI, TypeScript, React, Vercel, Terraform, GCP/AWS
    - £90,000-£150,000 + equity
    - Farringdon, London
    - Series A $16M

    *Edra <https://edra.ai/>*: builds AI systems that learn how a company
    actually operates and turn that knowledge into autonomous agents that run
    and improve those processes over time. Technically, this involves building
    long-running LLM and agent systems with strong evaluation frameworks,
    feedback loops, and orchestration layers that allow AI to reliably execute
    complex operational workflows in production.

    - Product Engineer
    - Python, TypeScript, FastAPI, Next.js, React
    - £80,000-£160,000 + equity
    - Holborn, London (5 days on-site)
    - Series A $30M

    *Apollo Research <https://www.apolloresearch.ai/>*: runs a hybrid research
    model: a non-profit arm conducting deep technical investigations into
    deceptive behaviour and alignment failures in frontier AI systems,
    alongside a commercial arm building evaluation frameworks and tooling to
    rigorously test and stress-test advanced models before deployment.

    - Full Stack Engineeer
    - Python, FastAPI, TypeScript, React
    - £100,000-£200,000
    - TBC, London (on-site)

    All specs attached (2 for Apollo) so have a read through and let me know
    your thoughts on each. As I mentioned, I think all of these are worth an
    initial chat.

    Looking forward to hearing from you.

    Many Thanks,

    *Will Laing*
    Co-Founder, Plan:it
    Co-Founder, London.js <https://www.meetup.com/london-js/>
    (+44) 07540489568

    *www.weareplanit.com <http://www.weareplanit.com>*
    Let's connect on LinkedIn! <https://www.linkedin.com/in/willhlaing/>
    """

    chunkifier = ParagraphChunkifier()
    chunks = chunkifier.chunk(text)
    print(len(chunks))


async def test_chunk_task():
    _prepare_email_chunks(
        email_account_id="0fabaceb-af22-4392-8e98-a843234982de",
        job_id="f6c82334-e888-4a05-8c6b-fee952dd0e71",
        filter_thread_ids=["16adbdec8aa7c2c8"],
    )


if __name__ == "__main__":
    # import pathlib

    # ids_path = pathlib.Path("app/data/json/message_ids.json")
    # out_path = pathlib.Path("app/data/json/all_emails_metadata.json")

    # message_ids = json.loads(ids_path.read_text())

    # # start small first
    # sample = message_ids[:500]

    # results = asyncio.run(fetch_messages_by_ids(sample, concurrency=15, rps=50))
    # out_path.write_text(json.dumps(results, indent=2))
    # print(f"Wrote {len(results)} messages to {out_path}")
    # asyncio.run(test_email_fetch())
    # asyncio.run(test_fetch_messages_by_thread())
    # expand_emails_per_thread(
    #     job_id="30e267d5-1957-46bc-9d83-5ea9439eeb5c",
    #     email_account_id="898c907d-d5e8-4a11-81cd-2f6a4d1a0a30",
    # )

    # fetch_email_content(
    #     job_id="30e267d5-1957-46bc-9d83-5ea9439eeb5c",
    #     email_account_id="898c907d-d5e8-4a11-81cd-2f6a4d1a0a30",
    # )
    # EMAIL_IDS = [
    #     # uuid.UUID("b5b78ca7-587d-459e-8622-fb2c92821bf3"),
    #     # uuid.UUID("07cf071e-e5fe-42f4-b0e0-678dde3215c8"),
    #     # uuid.UUID("9828fd56-b7c5-437b-9c6f-44094b7c0098"),
    #     # uuid.UUID("226a8f5d-6fda-44ac-8d6e-2318c8e1e872"),
    #     # uuid.UUID("4a8f7b2e-de9f-4dc1-85bf-c947535eb2f5"),
    #     # uuid.UUID("d6b5c74c-cf78-4ea0-b6f4-29daea1173f8"),
    #     # uuid.UUID(
    #     #     "25e0f360-4982-429b-8add-07de0fc3984b"
    #     # ),  # TODO: Handle Forwarded Email )*
    #     uuid.UUID("d27bdae0-a2d7-4ccd-85aa-a152082d67e3"),  # TODO: Amex security OT)P
    #     uuid.UUID("e4e12dc8-5348-485e-a0b9-50a5291bcc4c"),  # TODO: Company footer).
    #     uuid.UUID("484a77e4-63a3-4f97-a216-d7e8c81dd0e5"),  # TODO: Savils Footer).
    # ]

    # with Session(engine) as session:

    #     stmt = (
    #         select(Email, EmailContent)
    #         .join(EmailContent, Email.id == EmailContent.email_id)
    #         .where(col(EmailContent.email_id).in_(EMAIL_IDS))
    #     )
    #     res: Result = session.exec(stmt)
    #     rows: List[Tuple[Email, EmailContent]] = res.all()

    #     content_parser = GmailContentParser(normaliser=EmailNormaliser())

    #     for e, ec in rows:
    #         print(f"Processing: {ec.email_id}... From {e.sender}")
    #         normalized_text = content_parser.normaliser.normalise(
    #             text_plain=ec.text_plain, text_html=ec.text_html
    #         )
    #         print(f"Normalised Text: \n{normalized_text}")
    #         print(f"\n\n==========================================")

    # ==============================
    # MSG_ID = "195b366fe6f6c97f"
    # message_content = asyncio.run(fetch_messages_by_ids(message_ids=[MSG_ID]))
    # FILE_PATH: str = (
    #     "/Users/raman/Documents/Development/Projects/notes-lab/app/data/json"
    # )
    # with open(f"{FILE_PATH}/{MSG_ID}.json", "w") as file:
    #     json.dump(message_content, file)

    # parsed_email_content = GmailContentParser(normaliser=EmailNormaliser()).parse(
    #     message=message_content[0]
    # )
    # print(parsed_email_content)

    # Test email chunk prepare
    # asyncio.run(test_chunking_preparation_service())
    # test_chunking_algorithm()
    # asyncio.run(test_chunk_task())
    with Session(engine) as session:
        email_chunk_repo = EmailChunkRepository(session)
        email_chunks = email_chunk_repo.get_chunk_by_ids(
            ["001bbf9e-5981-47ed-8527-a2bad891f342"]
        )
        emb_svc = EmbeddingService(
            get_open_ai_client(),
            email_chunk_service=EmailChunkService(email_chunk_repo=email_chunk_repo),
        )
        embeddings = emb_svc.create_embedding_vectors_by_thread_id(
            thread_id="17ba640f6d1a8446"
        )
        pass
