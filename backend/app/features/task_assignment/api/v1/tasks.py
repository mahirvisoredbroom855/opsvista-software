from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Body

# Shared helpers
from backend.app.core.auth_deps import get_current_user, UserCtx

# Feature‑specific models & service
from backend.app.features.task_assignment.models.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskStatus
)
from backend.app.features.task_assignment.services.task_service import TaskService

# 🔐 Security scheme for Swagger (adds "Authorize" button)
bearer_scheme = HTTPBearer()

router = APIRouter(
    prefix="/tasks",
    tags=["Task Assignment"],
)

service = TaskService()




@router.get("/test")
def test_endpoint():
    print("🔍 TEST ENDPOINT HIT!")
    return {"message": "test works"}






# ───────────────────────── CREATE ───────────────────────── #

@router.post("/")
def create_task(
    data: TaskCreate,
    user: UserCtx = Depends(get_current_user),
    _: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    """Owner/Admin/Manager creates a new task for an assignee."""
    if user.role not in {"owner", "admin", "manager"}:
        raise HTTPException(403, "Only managers can assign tasks")
    
    return service.create_task(data, assigner_id=user.id)  # Remove user_token parameter

# ───────────────────────── LIST (assigned) ───────────────────────── #

@router.get(
    "/assigned/{assignee_id}",
    response_model=list[TaskResponse],
)
def list_tasks(
    assignee_id: UUID,
    user: UserCtx = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    """Worker sees their own tasks, managers can see anyone's."""
    
    # Convert user.id to UUID for comparison
    from uuid import UUID
    user_uuid = UUID(user.id)
    
    # Debug the comparison
    print(f"🔍 DEBUG - assignee_id: {assignee_id} (type: {type(assignee_id)})")
    print(f"🔍 DEBUG - user.id: {user.id} (type: {type(user.id)})")
    print(f"🔍 DEBUG - user_uuid: {user_uuid} (type: {type(user_uuid)})")
    print(f"🔍 DEBUG - user.role: {user.role}")
    print(f"🔍 DEBUG - Comparison result: {assignee_id == user_uuid}")
    
    if assignee_id != user_uuid and user.role not in {"owner", "admin", "manager"}:
        print("🔍 DEBUG - Access denied by endpoint logic")
        raise HTTPException(403, "Forbidden")
    
    print("🔍 DEBUG - Access granted, calling service")
    token = credentials.credentials
    return service.list_tasks(assignee_id, user_token=token)

# ───────────────────────── UPDATE ───────────────────────── #

@router.patch("/{task_id}")
def update_task(
    task_id: UUID,
    # patch: TaskUpdate,
    patch: dict = Body(...),
    user: UserCtx = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    print("🧪 PATCH BODY:", patch)
    print(f"🔍 API DEBUG - PATCH request for task: {task_id}")
    print(f"🔍 API DEBUG - User: {user.id} ({user.role})")
    print(f"🔍 API DEBUG - Patch payload: {patch}")

    
    try:
        result = service.update_task(task_id, patch, user.id, user.role)
        print(f"🔍 API DEBUG - Success: {result.dict()}")
        return result
    except Exception as e:
        print(f"🔍 API DEBUG - Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(422, f"Server-side error: {str(e)}")

# ───────────────────────── METRICS ───────────────────────── #

@router.get("/metrics")
def get_task_metrics(
    user: UserCtx = Depends(get_current_user),
    _: HTTPAuthorizationCredentials = Security(bearer_scheme)
):
    """Return high‑level KPIs for dashboard; managers only."""
    if user.role not in {"owner", "admin", "manager"}:
        raise HTTPException(403, "Managers only")
    
    return service.get_metrics()  # Remove user_token parameter


