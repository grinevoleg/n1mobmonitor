from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from app.config import settings

# Basic Auth для администратора (только переменные окружения / .env)
admin_auth = HTTPBasic(auto_error=False)


async def get_admin_user(
    credentials: HTTPBasicCredentials = Depends(admin_auth),
):
    """Проверка ADMIN_USERNAME / ADMIN_PASSWORD из .env."""
    username = settings.admin_username
    password = settings.admin_password

    if not credentials or not secrets.compare_digest(
        credentials.username.encode("utf-8"), username.encode("utf-8")
    ) or not secrets.compare_digest(
        credentials.password.encode("utf-8"), password.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )

    return {"username": credentials.username}
