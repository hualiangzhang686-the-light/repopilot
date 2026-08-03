from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    username: str
    active: bool = True


def login(username: str, password: str) -> User | None:
    """Validate the demo account and return the authenticated user."""
    if username == "demo" and password == "correct-horse":
        return User(username=username)
    return None
