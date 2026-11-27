from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository


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

    def delete_user(self, user: User) -> None:

        try:
            self.user_repository.delete_user(user)

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise
    def get_user_or_404(self, user_id: int) -> User:
        return self.user_repository.get_user_or_404(user_id)