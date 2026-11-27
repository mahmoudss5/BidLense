import logging

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def create_default_admin() -> None:
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        logger.warning(
            "ADMIN_EMAIL/ADMIN_PASSWORD are not set; no default admin was created"
        )
        return

    email = settings.ADMIN_EMAIL.strip().lower()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role != UserRole.ADMIN.value:
                logger.warning(
                    "ADMIN_EMAIL already belongs to a non-admin account; "
                    "it was not automatically promoted"
                )
            return

        admin = User(
            email=email,
            full_name=settings.ADMIN_FULL_NAME,
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.info("Default admin account created: %s", email)
    finally:
        db.close()
