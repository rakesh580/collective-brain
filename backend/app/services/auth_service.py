import logging
import random
import string
from datetime import datetime, timedelta
from uuid import uuid4

from passlib.context import CryptContext
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.user import UserRecord

logger = logging.getLogger(__name__)
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
            auth_provider="local",
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
        """Authenticate by username/email + password.

        Returns the user on success, or raises ValueError with a specific
        message so the caller can tell the user what went wrong.
        """
        user = (
            db.query(UserRecord)
            .filter(
                (UserRecord.username == username) | (UserRecord.email == username)
            )
            .first()
        )
        if not user:
            raise ValueError("No account found with that username or email")
        if not user.is_active:
            raise ValueError("This account has been deactivated")
        if not user.password_hash:
            # OAuth-only user — no password set
            raise ValueError(
                "This account uses Google Sign-In. Please use the Google button to log in"
            )
        if not self.verify_password(password, user.password_hash):
            raise ValueError("Incorrect password")
        user.last_login = datetime.utcnow()
        db.commit()
        return user

    # ------------------------------------------------------------------
    # Google OAuth
    # ------------------------------------------------------------------
    def google_authenticate(
        self,
        db: Session,
        google_id_token: str,
        google_client_id: str,
    ) -> UserRecord:
        """Verify a Google ID token, then find or create the user."""
        from google.oauth2 import id_token as google_id_token_mod
        from google.auth.transport import requests as google_requests

        try:
            idinfo = google_id_token_mod.verify_oauth2_token(
                google_id_token,
                google_requests.Request(),
                google_client_id,
            )
        except ValueError as e:
            raise ValueError(f"Invalid Google token: {e}")

        google_sub = idinfo["sub"]
        email = idinfo.get("email")
        email_verified = idinfo.get("email_verified", False)
        name = idinfo.get("name", "")
        picture = idinfo.get("picture")

        if not email or not email_verified:
            raise ValueError("Google account email is not verified")

        # 1. Returning Google user
        user = db.query(UserRecord).filter(UserRecord.google_id == google_sub).first()
        if user:
            if not user.is_active:
                raise ValueError("This account has been deactivated")
            user.last_login = datetime.utcnow()
            if picture and not user.avatar_url:
                user.avatar_url = picture
            db.commit()
            return user

        # 2. Existing user with same email — link Google account
        user = db.query(UserRecord).filter(UserRecord.email == email).first()
        if user:
            if not user.is_active:
                raise ValueError("This account has been deactivated")
            user.google_id = google_sub
            user.auth_provider = (
                "google+local" if user.password_hash else "google"
            )
            user.last_login = datetime.utcnow()
            if picture and not user.avatar_url:
                user.avatar_url = picture
            db.commit()
            return user

        # 3. Brand new user
        base_username = email.split("@")[0].replace(".", "").replace("+", "")[:30]
        username = base_username
        suffix = 1
        while db.query(UserRecord).filter(UserRecord.username == username).first():
            username = f"{base_username}{suffix}"
            suffix += 1

        user = UserRecord(
            id=str(uuid4()),
            username=username,
            email=email,
            password_hash=None,
            display_name=name or username,
            avatar_url=picture,
            google_id=google_sub,
            auth_provider="google",
            is_active=True,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    # ------------------------------------------------------------------
    # Password Reset
    # ------------------------------------------------------------------
    def generate_reset_code(self, db: Session, email: str) -> str:
        """Generate a 6-digit reset code for the given email.

        Returns the code (to be sent via email).
        Raises ValueError if no account found.
        """
        user = db.query(UserRecord).filter(UserRecord.email == email).first()
        if not user:
            raise ValueError("No account found with that email address")
        if not user.is_active:
            raise ValueError("This account has been deactivated")
        if user.auth_provider == "google" and not user.password_hash:
            raise ValueError(
                "This account uses Google Sign-In and has no password to reset"
            )

        import secrets as _secrets
        code = "".join(_secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        user.reset_code = pwd_context.hash(code)
        user.reset_code_expires = datetime.utcnow() + timedelta(minutes=15)
        db.commit()
        return code

    def verify_reset_code(
        self, db: Session, email: str, code: str, new_password: str
    ) -> UserRecord:
        """Verify the reset code and update the password.

        Raises ValueError on any failure.
        """
        user = db.query(UserRecord).filter(UserRecord.email == email).first()
        if not user:
            raise ValueError("No account found with that email address")
        if not user.reset_code or not pwd_context.verify(code, user.reset_code):
            raise ValueError("Invalid verification code")
        if user.reset_code_expires and user.reset_code_expires < datetime.utcnow():
            raise ValueError("Verification code has expired")

        user.password_hash = self.hash_password(new_password)
        user.reset_code = None
        user.reset_code_expires = None
        # If this was a Google-only user setting a password for the first time
        if user.auth_provider == "google":
            user.auth_provider = "google+local"
        db.commit()
        db.refresh(user)
        return user
