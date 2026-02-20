from datetime import datetime
from time import timezone
from sqlmodel import select
from app.models.models import WorkflowJob
from app.repositories.job_repository import JobRepository
from app.enums import ResourceType, JobType, JobStatus
import uuid


class JobService:

    def __init__(self, job_repository: JobRepository):
        self.job_repo = job_repository

    def has_running_sync_job(self, email_account_id: uuid.UUID) -> bool:
        """
        Check if there is a running sync job for the given email account.

        Args:
            email_account_id: UUID of the email account

        Returns:
            True if there is a running or queued job, False otherwise
        """
        job = self.job_repo.find_job_by_resource(
            resource_id=email_account_id,
            resource_type=ResourceType.email_account,
            job_type=JobType.mailbox_sync,
            statuses=[JobStatus.queued, JobStatus.running],
        )
        return job is not None

    def get_or_create_active_job(
        self, resource_type: ResourceType, resource_id: uuid.UUID, job_type: JobType
    ) -> (WorkflowJob, bool):
        workflow_job = self.job_repo.find_job_by_resource(
            resource_id=resource_id,
            resource_type=resource_type,
            job_type=job_type,
            statuses=[JobStatus.queued, JobStatus.running],
        )

        if not workflow_job:
            print(
                f"Unable to fetch active job for job_type={job_type}, resource_type={resource_type}, resource_id={resource_id}"
            )
            workflow_job = self.job_repo.create(
                resource_id=resource_id,
                resource_type=resource_type,
                job_type=job_type,
                job_status=JobStatus.queued,
            )
            return workflow_job, True

        return workflow_job, False

    def update_job(
        self,
        job_id: uuid.UUID,
        *,
        status=None,
        error_message=None,
        progress_current=None,
        progress_total=None,
        cursor=None,
        started_at=None,
        completed_at=None,
    ) -> WorkflowJob:

        job = self.job_repo.find_by_id(id=job_id)

        if status is not None:
            job.status = status

        # if progress_current is not None:
        #     job.progress_current = progress_current

        # if progress_total is not None:
        #     job.progress_total = progress_total

        # if cursor is not None:
        #     job.cursor = cursor

        if error_message is not None:
            job.error_message = error_message

        # if started_at is not None:
        #     job.started_at = started_at

        # if completed_at is not None:
        #     job.completed_at = completed_at

        # job.last_heartbeat_at = datetime.now(timezone.utc)
        job = self.job_repo.update(job)

        return job
