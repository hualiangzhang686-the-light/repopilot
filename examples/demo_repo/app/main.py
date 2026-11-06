from app.auth import login


def authenticate() -> bool:
    return login("demo", "correct-horse") is not None
