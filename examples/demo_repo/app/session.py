from datetime import datetime, timedelta

from app.auth import User


SESSION_TTL_SECONDS = 1800


def create_session(user: User, created_at: datetime) -> dict[str, object]:
    return {"username": user.username, "created_at": created_at}


def is_session_expired(created_at: datetime, now: datetime) -> bool:
    return now >= created_at + timedelta(seconds=SESSION_TTL_SECONDS)
