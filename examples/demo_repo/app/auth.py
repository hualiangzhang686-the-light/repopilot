from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    username: str
    active: bool = True


def login(username: str, password: str) -> User | None:
    """演示登录逻辑：验证固定测试账号并返回用户。"""
    if username == "demo" and password == "correct-horse":
        return User(username=username)
    return None

