from pydantic import BaseModel, Field
from enum import Enum
from uuid import UUID
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel



class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    overdue = "overdue"

class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

class TaskCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    assignee_id: UUID
    due_date: date
    priority: TaskPriority = TaskPriority.medium

class TaskUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    status: Optional[TaskStatus]
    priority: Optional[TaskPriority]
    due_date: Optional[date]

class TaskResponse(BaseModel):
    task_id: UUID
    title: str
    description: Optional[str]
    assigner_id: UUID
    assignee_id: UUID
    created_at: datetime
    due_date: date
    status: TaskStatus
    priority: TaskPriority
    updated_at: datetime
    done_at: Optional[datetime]
