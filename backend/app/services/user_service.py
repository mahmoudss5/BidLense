from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.api.deps import get_current_user, require_admin
from app.api.routes import admin
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import MeUpdate, AdminUserUpdate


class UserService:

    def __init__(
        self,
        db: Session,
        user_repository: UserRepository
    ):
        self.db = db
        self.user_repository = user_repository

    def get_user_by_id(self, user_id: int) -> User | None:

        return self.user_repository.get_user_by_id(user_id)

    def create_user(self, user: User) -> User:

        try:
            created_user = self.user_repository.create_user(user)

            self.db.commit()
            self.db.refresh(created_user)

            return created_user

        except Exception:
            self.db.rollback()
            raise

    def delete_user(self, user_id: int) -> None:
        target = self.get_user_or_404(user_id)

        if target.id == admin.id:
            raise HTTPException(status_code=400, detail="You cannot delete your own admin account")

        removing_admin_access = (
                target.role == UserRole.ADMIN.value and target.is_active
        )
        admin.protect_last_admin(self.db, target, removing_admin_access)

        self.db.delete(target)
        self.db.commit()



    def get_user_or_404(self, user_id: int) -> User:
        return self.user_repository.get_user_or_404(user_id)


    def update_user(self, payload: MeUpdate, current_user: User = Depends(get_current_user)  ):
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No changes provided",
            )

        if "full_name" in changes:
            current_user.full_name = changes["full_name"].strip()
        if "password" in changes:
            current_user.hashed_password = hash_password(changes["password"])

        self.db.commit()
        self.db.refresh(current_user)
        return current_user

    def admin_update_user(self,user_id: int,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin) ):

        target = self.get_user_or_404(user_id)
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
        self.protect_last_admin(self.db, target, removing_admin_access)

        if "email" in changes:
            email = str(changes["email"]).lower()
            duplicate = (
                self.db.query(User)
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

        self.db.commit()
        self.db.refresh(target)
        return target
