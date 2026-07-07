import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from db import engine, pwd_context
from models import AdminUser

# In a real deployment this should come from an environment variable set once
# on the pack house PC. A random one is generated on first import so the
# server at least doesn't ship with a hardcoded shared secret.
SECRET_KEY = os.environ.get("LW_SECRET_KEY") or os.urandom(32).hex()
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> AdminUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    with Session(engine) as session:
        user = session.exec(select(AdminUser).where(AdminUser.username == username)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user
