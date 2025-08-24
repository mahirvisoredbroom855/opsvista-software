from __future__ import annotations

from datetime import datetime, date
from typing import List
from uuid import UUID
from enum import Enum
import json
import logging
from app.core.supabase_client import supabase as service_supabase
from app.core.supabase_client import supabase
from app.features.task_assignment.models.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskStatus,
    TaskPriority,
)

TABLE = "tasks"

logger = logging.getLogger(__name__)


class TaskService:
    # ─────────────────────────────── UTIL ──────────────────────────────── #
    @staticmethod
    def _serialize_uuid(val: UUID | str) -> str:
        return str(val)

    @staticmethod
    def _serialize_datetime(val: datetime) -> str:
        return val.isoformat()

    # ─────────────────────────────── CREATE ──────────────────────────────── #
    @staticmethod
    def create_task(data: TaskCreate, assigner_id: UUID) -> TaskResponse:
        """Insert a new task. Only called by owner / admin / manager."""
        from app.core.supabase_client import service_supabase
        
        def serialize(val):
            if isinstance(val, UUID):
                return str(val)
            elif isinstance(val, (datetime, date)):
                return val.isoformat()
            elif isinstance(val, Enum):
                return val.value
            return val

        # Serialize TaskCreate data
        record = {k: serialize(v) for k, v in data.dict().items()}
        record["assigner_id"] = str(assigner_id)
        record["status"] = TaskStatus.pending.value
        record["created_at"] = datetime.utcnow().isoformat()
        record["updated_at"] = datetime.utcnow().isoformat()

        # Optional: log before inserting
        print("📦 Serialized task payload:", record)

        resp = service_supabase.table(TABLE).insert(record).execute()

        if not resp.data:
            raise RuntimeError(resp.error_message or "Insert failed")

        return TaskResponse(**resp.data[0])





    # ─────────────────────────────── LIST ──────────────────────────────── #
    @staticmethod
    def list_tasks(assignee_id: UUID, user_token: str = None) -> List[TaskResponse]:
        """Return tasks assigned to a user, ordered by due_date."""
        logger.debug(f"[LIST_TASKS] Fetching tasks for assignee: {assignee_id}")
        print(f"🔍 BACKEND DEBUG - Assignee ID: {assignee_id}")
        
        # Use service client which bypasses RLS - temporary fix
        from app.core.supabase_client import service_supabase
        
        # First get the tasks
        resp = (
            service_supabase.table(TABLE)
            .select("*")
            .eq("assignee_id", TaskService._serialize_uuid(assignee_id))
            .order("due_date")
            .execute()
        )
        print(f"🔍 BACKEND DEBUG - Service client returned {len(resp.data)} tasks")
        
        tasks = []
        for row in resp.data:
            task_data = dict(row)
            
            # Get the assignee name separately
            try:
                user_resp = (
                    service_supabase.table("users")
                    .select("full_name")
                    .eq("id", row["assignee_id"])
                    .single()
                    .execute()
                )
                task_data["assignee_name"] = user_resp.data.get("full_name", "Unknown User")
            except Exception as e:
                print(f"🔍 BACKEND DEBUG - Could not get user name: {e}")
                task_data["assignee_name"] = "Unknown User"
            
            tasks.append(TaskResponse(**task_data))
        
        return tasks

        # ──────────────────────────── UPDATE ───────────────────────────── #
    @staticmethod
    def update_task(task_id: UUID, patch: TaskUpdate, user_id: UUID, role: str) -> TaskResponse:
        """Update task status or fields based on role."""
        from app.features.task_assignment.models.task import TaskStatus

        task_id_str = TaskService._serialize_uuid(task_id)
        user_id_str = TaskService._serialize_uuid(user_id)

        print(f"🔍 UPDATE DEBUG - Task ID: {task_id_str}")
        print(f"🔍 UPDATE DEBUG - User ID: {user_id_str}")
        print(f"🔍 UPDATE DEBUG - User Role: {role}")
        print(f"🔍 UPDATE DEBUG - Patch data: {patch}")

        # Use service client to avoid RLS issues for now
        from app.core.supabase_client import service_supabase
        
        current = (
            service_supabase.table(TABLE)
            .select("*")
            .eq("task_id", task_id_str)
            .single()
            .execute()
            .data
        )
        
        if not current:
            print(f"🔍 UPDATE DEBUG - Task not found: {task_id_str}")
            raise RuntimeError("Task not found")
        
        print(f"🔍 UPDATE DEBUG - Current task: {current}")
        print(f"🔍 UPDATE DEBUG - Current assignee: {current['assignee_id']}")

        is_privileged = role in {"owner", "admin", "manager"}
        if not is_privileged and current["assignee_id"] != user_id_str:
            print(f"🔍 UPDATE DEBUG - Permission denied: user {user_id_str} trying to update task assigned to {current['assignee_id']}")
            raise PermissionError("Forbidden")

        changes = {k: v for k, v in patch.items() if v is not None}
        print(f"🔍 UPDATE DEBUG - Changes to apply: {changes}")
        
        if not changes:
            print(f"🔍 UPDATE DEBUG - No changes to apply")
            return TaskResponse(**current)

        # Worker logic
        if not is_privileged:
            if set(changes) - {"status"}:
                print(f"🔍 UPDATE DEBUG - Worker trying to change non-status fields: {set(changes) - {'status'}}")
                raise PermissionError("Only status can be changed")
            if "status" in changes and changes["status"] not in {TaskStatus.in_progress.value, TaskStatus.done.value}:
                print(f"🔍 UPDATE DEBUG - Invalid status change: {changes['status']}")
                raise PermissionError("Invalid status")

        # Apply timestamp
        changes["updated_at"] = TaskService._serialize_datetime(datetime.utcnow())
        
        # Set done_at timestamp when marking as done
        if changes.get("status") == TaskStatus.done.value:
            changes["done_at"] = TaskService._serialize_datetime(datetime.utcnow())
            print(f"🔍 UPDATE DEBUG - Setting done_at: {changes['done_at']}")

        print(f"🔍 UPDATE DEBUG - Final changes: {changes}")

        try:
            print(f"🚨 Trying to update task {task_id_str} with changes:", changes)
            resp = (
                service_supabase.table(TABLE)
                .update(changes)
                .eq("task_id", task_id_str)
                .execute()
            )
            print("🧪 Supabase Update Response:", resp)

            updated = resp.data[0]
            print(f"🔍 UPDATE DEBUG - Update successful: {updated}")
            return TaskResponse(**updated)
        except Exception as e:
            print(f"🔍 UPDATE DEBUG - Update failed: {e}")
            raise




    # ──────────────────────────── METRICS ───────────────────────────── #
    @staticmethod
    def get_metrics() -> dict:
        """Compute task KPIs."""
        # Use service client for admin operations
        from app.core.supabase_client import service_supabase
        resp = service_supabase.table(TABLE).select("status, done_at, created_at").execute()
        # ... rest of your original code

    
        q = resp.data or []

        total = len(q)
        completed = sum(1 for r in q if r["status"] == "done")
        overdue = sum(1 for r in q if r["status"] == "overdue")

        avg_hours = (
            sum(
                (
                    datetime.fromisoformat(r["done_at"]) - datetime.fromisoformat(r["created_at"])
                ).total_seconds()
                for r in q if r["status"] == "done" and r["done_at"] and r["created_at"]
            ) / 3600 / completed
            if completed else 0
        )

        return {
            "total": total,
            "completed": completed,
            "overdue": overdue,
            "completion_rate": round(completed / total * 100, 1) if total else 0,
            "avg_completion_hours": round(avg_hours, 2),
        }
    
    # ──────────────────────────── DELETE ───────────────────────────── #
    @staticmethod
    def delete_task(task_id: UUID) -> bool:
        print(f"🗑️ SERVICE - Attempting to delete task: {task_id}")

        try:
            from app.core.supabase_client import service_supabase

            # Check existence
            check = (
                service_supabase
                .table("tasks")
                .select("*")
                .eq("task_id", str(task_id))
                .maybe_single()
                .execute()
            )
            print("🕵️‍♂️ Task found before delete:", check.data)

            if not check.data:
                print("❌ Task not found — aborting delete.")
                return False

            # Proceed to delete
            response = (
                service_supabase
                .table("tasks")
                .delete()
                .eq("task_id", str(task_id))
                .execute()
            )

            print("📄 Supabase delete response:", response)
            return bool(response.data)

        except Exception as e:
            print("❌ Delete failed with exception:", e)
            return False








    # ──────────────────────────── CRON JOB ───────────────────────────── #
    @staticmethod
    def mark_overdue() -> int:
        """Mark tasks as overdue if past due_date and not done."""
        today = datetime.utcnow().date().isoformat()
        resp = (
            supabase.table(TABLE)
            .update({
                "status": TaskStatus.overdue.value,
                "updated_at": TaskService._serialize_datetime(datetime.utcnow()),
            })
            .lt("due_date", today)
            .neq("status", TaskStatus.done.value)
            .execute()
        )
        return resp.count or 0
    


    @staticmethod
    def list_all_tasks() -> List[TaskResponse]:
        """Return all tasks for managers, ordered by due_date."""
        print(f"🔍 BACKEND DEBUG - Fetching all tasks for manager")
        
        # Use service client which bypasses RLS
        from app.core.supabase_client import service_supabase
        
        # Get all tasks
        resp = (
            service_supabase.table(TABLE)
            .select("*")
            .order("due_date")
            .execute()
        )
        print(f"🔍 BACKEND DEBUG - Service client returned {len(resp.data)} total tasks")
        
        tasks = []
        for row in resp.data:
            task_data = dict(row)
            
            # Get the assignee name separately
            try:
                user_resp = (
                    service_supabase.table("users")
                    .select("full_name")
                    .eq("id", row["assignee_id"])
                    .single()
                    .execute()
                )
                task_data["assignee_name"] = user_resp.data.get("full_name", "Unknown User")
            except Exception as e:
                print(f"🔍 BACKEND DEBUG - Could not get user name: {e}")
                task_data["assignee_name"] = "Unknown User"
            
            tasks.append(TaskResponse(**task_data))
        
        return tasks

