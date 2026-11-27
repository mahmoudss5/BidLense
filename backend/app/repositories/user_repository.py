from fastapi import HTTPException
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole


class UserRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, email: EmailStr) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()

    def get_All_users(self, skip: int = 0, limit: int = 100, search: str | None = None, role: UserRole | None = None, is_active: bool | None = None) -> list[User]:
        query = self.db.query(User)

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

    def get_user_or_404(self, user_id: int) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user