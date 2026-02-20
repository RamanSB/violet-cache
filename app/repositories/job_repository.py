from sqlmodel import Session, select
from app.models.models import WorkflowJob
from app.enums import JobStatus, ResourceType, JobType
from typing import List
import uuid


class JobRepository:

    def __init__(self, session: Session):
        self.session = session

    def find_job_by_resource(
        self,
        resource_id: uuid.UUID,
        resource_type: ResourceType,
        job_type: JobType,
        statuses: List[JobStatus] | None = None,
    ) -> WorkflowJob | None:
        """
        Find a job for a specific resource with optional status filtering.

        Args:
            resource_id: ID of the resource (e.g., email_account_id)
            resource_type: Type of resource (e.g., ResourceType.email_account)
            job_type: Type of job (e.g., JobType.mailbox_sync)
            statuses: Optional list of statuses to filter by. If None, returns any job regardless of status.

        Returns:
            WorkflowJob if found, None otherwise
        """
        statement = select(WorkflowJob).where(
            WorkflowJob.resource_id == resource_id,
            WorkflowJob.resource_type == resource_type,
            WorkflowJob.job_type == job_type,
        )

        if statuses:
            statement = statement.where(WorkflowJob.status.in_(statuses))

        return self.session.exec(statement).first()

    def create(
        self,
        resource_id: uuid.UUID,
        resource_type: ResourceType,
        job_type: JobType,
        job_status: JobStatus,
    ):
        workflow_job = WorkflowJob(
            resource_id=resource_id,
            resource_type=resource_type,
            job_type=job_type,
            status=job_status,
        )
        self.session.add(workflow_job)
        self.session.commit()
        self.session.refresh(workflow_job)
        return workflow_job

    def update(self, job: WorkflowJob) -> WorkflowJob:
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def find_by_id(self, id: uuid.UUID) -> WorkflowJob | None:
        return self.session.get(WorkflowJob, id)
