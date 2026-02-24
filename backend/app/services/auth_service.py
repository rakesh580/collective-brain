from datetime import datetime, timedelta
from uuid import uuid4

from passlib.context import CryptContext
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.user import UserRecord

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, settings: Settings):
        self.secret = settings.jwt_secret
        self.algorithm = settings.jwt_algorithm
        self.expire_minutes = settings.jwt_expire_minutes

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    def create_token(self, user_id: str) -> str:
        expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)
        payload = {"sub": user_id, "exp": expire}
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def decode_token(self, token: str) -> str | None:
        """Returns user_id or None if invalid."""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload.get("sub")
        except JWTError:
            return None

    def register(
        self,
        db: Session,
        username: str,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> UserRecord:
        if db.query(UserRecord).filter(UserRecord.username == username).first():
            raise ValueError("Username already taken")
        if db.query(UserRecord).filter(UserRecord.email == email).first():
            raise ValueError("Email already registered")

        user = UserRecord(
            id=str(uuid4()),
            username=username,
            email=email,
            password_hash=self.hash_password(password),
            display_name=display_name or username,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def authenticate(
        self, db: Session, username: str, password: str
    ) -> UserRecord | None:
        user = (
            db.query(UserRecord)
            .filter(
                (UserRecord.username == username) | (UserRecord.email == username)
            )
            .first()
        )
        if not user or not user.is_active:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        user.last_login = datetime.utcnow()
        db.commit()
        return user
