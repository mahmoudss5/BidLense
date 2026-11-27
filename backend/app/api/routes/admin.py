from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    AdminUserCreate,
    AdminUserUpdate,
    DashboardStats,
    UserOut,
)
from app.tasks.celery_app import celery_app
from app.tasks.tasks import send_welcome_email

router = APIRouter(prefix="/admin", tags=["Admin"])


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def protect_last_admin(db: Session, target: User, removing_admin_access: bool) -> None:
    if not removing_admin_access:
        return

    active_admin_count = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN.value, User.is_active.is_(True))
        .count()
    )
    if target.role == UserRole.ADMIN.value and target.is_active and active_admin_count <= 1:
        raise HTTPException(
            status_code=400,
            detail="You cannot remove or deactivate the last active admin",
        )


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    total = db.query(User).count()
    active = db.query(User).filter(User.is_active.is_(True)).count()
    admins = db.query(User).filter(User.role == UserRole.ADMIN.value).count()
    regular = db.query(User).filter(User.role == UserRole.USER.value).count()

    return DashboardStats(
        total_users=total,
        active_users=active,
        inactive_users=total - active,
        admin_users=admins,
        regular_users=regular,
    )


@router.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, description="Search by email or name"),
    role: UserRole | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(User)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (User.email.ilike(term)) | (User.full_name.ilike(term))
        )
    if role is not None:
        query = query.filter(User.role == role.value)
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))

    return query.order_by(User.id.desc()).offset(skip).limit(limit).all()


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_user_or_404(db, user_id)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    email = str(payload.email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email is already registered")

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=payload.role.value,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = get_user_or_404(db, user_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)

    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")

    if target.id == admin.id:
        removing_own_admin_access = (
            changes.get("role") == UserRole.USER
            or changes.get("is_active") is False
        )
        if removing_own_admin_access:
            raise HTTPException(
                status_code=400,
                detail="You cannot demote or deactivate your own admin account",
            )

    new_role = changes.get("role", UserRole(target.role))
    new_is_active = changes.get("is_active", target.is_active)
    removing_admin_access = (
        target.role == UserRole.ADMIN.value
        and target.is_active
        and (new_role == UserRole.USER or not new_is_active)
    )
    protect_last_admin(db, target, removing_admin_access)

    if "email" in changes:
        email = str(changes["email"]).lower()
        duplicate = (
            db.query(User)
            .filter(User.email == email, User.id != target.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Email is already in use")
        target.email = email

    if "full_name" in changes:
        target.full_name = changes["full_name"].strip()
    if "password" in changes:
        target.hashed_password = hash_password(changes["password"])
    if "role" in changes:
        target.role = changes["role"].value
    if "is_active" in changes:
        target.is_active = changes["is_active"]

    db.commit()
    db.refresh(target)
    return target


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = get_user_or_404(db, user_id)

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin account")

    removing_admin_access = (
        target.role == UserRole.ADMIN.value and target.is_active
    )
    protect_last_admin(db, target, removing_admin_access)

    db.delete(target)
    db.commit()
    return None


@router.post("/users/{user_id}/send-welcome-email")
def queue_welcome_email(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    target = get_user_or_404(db, user_id)
    try:
        task = send_welcome_email.delay(target.id, target.email)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the background task broker",
        ) from exc

    return {"task_id": task.id, "message": "Welcome email task queued"}


@router.get("/tasks/{task_id}")
def get_task_status(
    task_id: str,
    _: User = Depends(require_admin),
):
    task = celery_app.AsyncResult(task_id)
    response = {"task_id": task_id, "status": task.status}
    if task.successful():
        response["result"] = task.result
    return response
