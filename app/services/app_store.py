import httpx
import random
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)


# Пул User-Agent для ротации (реальные браузеры и устройства)
USER_AGENTS = [
    # macOS Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    # macOS Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    # iPad Safari
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    # Windows Chrome (для разнообразия)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    """Возвращает случайный User-Agent из пула"""
    return random.choice(USER_AGENTS)


class AppStoreClient:
    """Клиент для iTunes Lookup API"""

    BASE_URL = "https://itunes.apple.com"
    TIMEOUT = 30  # секунд
    MAX_RETRIES = 3
    BASE_DELAY = 60  # секунд (1 минута)

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    async def startup(self) -> None:
        """Один долгоживущий клиент на процесс (вызывать из lifespan)."""
        async with self._client_lock:
            if self._client is not None:
                return
            lim = max(1, settings.http_max_connections)
            self._client = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                limits=httpx.Limits(
                    max_keepalive_connections=min(10, lim),
                    max_connections=lim,
                ),
            )

    async def shutdown(self) -> None:
        async with self._client_lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    async def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполнение запроса с ротацией User-Agent и обработкой 429

        Args:
            params: Параметры запроса

        Returns:
            dict с результатом или ошибкой
        """
        last_error = None
        client = await self._ensure_client()

        for attempt in range(self.MAX_RETRIES):
            try:
                user_agent = get_random_user_agent()
                response = await client.get(
                    f"{self.BASE_URL}/lookup",
                    params=params,
                    headers={"User-Agent": user_agent},
                )

                if response.status_code == 429:
                    retry_after = int(
                        response.headers.get("Retry-After", self.BASE_DELAY * (2**attempt))
                    )
                    logger.warning("Получен 429. Ожидание %s секунд...", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException as e:
                last_error = f"Превышено время ожидания: {str(e)}"
                logger.warning("Таймаут запроса (попытка %s): %s", attempt + 1, last_error)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after = self.BASE_DELAY * (2**attempt)
                    logger.warning("Получен 429. Ожидание %s секунд...", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                last_error = f"HTTP ошибка: {str(e)}"
                break

            except httpx.HTTPError as e:
                last_error = f"HTTP ошибка: {str(e)}"
                logger.warning("Ошибка запроса (попытка %s): %s", attempt + 1, last_error)

            except Exception as e:
                last_error = f"Неизвестная ошибка: {str(e)}"
                logger.error("Неожиданная ошибка: %s", last_error)
                break

        return {"error": last_error or "Неизвестная ошибка после всех попыток"}

    async def lookup_by_bundle_id(self, bundle_id: str) -> Dict[str, Any]:
        """
        Поиск приложения по Bundle ID

        Returns:
            dict с информацией о приложении или ошибкой
        """
        try:
            data = await self._make_request({"bundleId": bundle_id})

            if "error" in data:
                return {
                    "status": "error",
                    "name": None,
                    "version": None,
                    "message": data["error"],
                }

            if data.get("resultCount", 0) > 0:
                app_data = data["results"][0]
                return {
                    "status": "available",
                    "name": app_data.get("trackName"),
                    "version": app_data.get("version"),
                    "icon_url": app_data.get("artworkUrl512"),  # 512x512 icon
                    "description": app_data.get("description"),
                    "bundle_id": app_data.get("bundleId"),
                    "app_id": app_data.get("trackId"),
                    "price": app_data.get("price", 0),
                    "currency": app_data.get("currency"),
                    "genre": app_data.get("primaryGenreName"),
                    "release_date": app_data.get("releaseDate"),
                    "message": "Приложение найдено",
                }
            return {
                "status": "unavailable",
                "name": None,
                "version": None,
                "message": f"Приложение с Bundle ID '{bundle_id}' не найдено",
            }

        except Exception as e:
            logger.error("Ошибка lookup_by_bundle_id: %s", e)
            return {
                "status": "error",
                "name": None,
                "version": None,
                "message": f"Неизвестная ошибка: {str(e)}",
            }

    async def lookup_by_app_id(self, app_id: int) -> Dict[str, Any]:
        """
        Поиск приложения по App ID

        Returns:
            dict с информацией о приложении или ошибкой
        """
        try:
            data = await self._make_request({"id": app_id})

            if "error" in data:
                return {
                    "status": "error",
                    "name": None,
                    "version": None,
                    "message": data["error"],
                }

            if data.get("resultCount", 0) > 0:
                app_data = data["results"][0]
                return {
                    "status": "available",
                    "name": app_data.get("trackName"),
                    "version": app_data.get("version"),
                    "icon_url": app_data.get("artworkUrl512"),  # 512x512 icon
                    "description": app_data.get("description"),
                    "bundle_id": app_data.get("bundleId"),
                    "app_id": app_data.get("trackId"),
                    "price": app_data.get("price", 0),
                    "currency": app_data.get("currency"),
                    "genre": app_data.get("primaryGenreName"),
                    "release_date": app_data.get("releaseDate"),
                    "message": "Приложение найдено",
                }
            return {
                "status": "unavailable",
                "name": None,
                "version": None,
                "message": f"Приложение с ID '{app_id}' не найдено",
            }

        except Exception as e:
            logger.error("Ошибка lookup_by_app_id: %s", e)
            return {
                "status": "error",
                "name": None,
                "version": None,
                "message": f"Неизвестная ошибка: {str(e)}",
            }


# Singleton экземпляр
app_store_client = AppStoreClient()
