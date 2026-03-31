import asyncio
import httpx
import random
import re
import logging
from typing import Optional, Dict, Any, List, Tuple

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


def _parse_lookup_countries(raw: str) -> List[str]:
    out = [c.strip().lower() for c in (raw or "").split(",") if c.strip()]
    return out if out else ["us"]


def _version_sort_key(version: Optional[str]) -> Tuple[int, ...]:
    """Сравнение версий вроде 1.0.2 без внешних зависимостей."""
    if not version:
        return (0,)
    nums = [int(x) for x in re.findall(r"\d+", str(version))]
    return tuple(nums) if nums else (0,)


def _norm_store_release_date(app_data: Dict[str, Any]) -> Optional[str]:
    v = app_data.get("currentVersionReleaseDate")
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _available_payload(raw: Dict[str, Any], country: str) -> Dict[str, Any]:
    return {
        "status": "available",
        "name": raw.get("trackName"),
        "version": raw.get("version"),
        "icon_url": raw.get("artworkUrl512"),
        "description": raw.get("description"),
        "bundle_id": raw.get("bundleId"),
        "app_id": raw.get("trackId"),
        "price": raw.get("price", 0),
        "currency": raw.get("currency"),
        "genre": raw.get("primaryGenreName"),
        "release_date": raw.get("releaseDate"),
        "store_release_date": _norm_store_release_date(raw),
        "message": "Приложение найдено",
        "_country": country,
        "_raw": raw,
    }


def _pick_best_available(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Берём витрину с наибольшей версией; при равенстве — более позднюю дату релиза текущей версии."""
    ok = [c for c in candidates if c.get("status") == "available" and c.get("_raw")]
    if not ok:
        raise ValueError("no available candidates")

    def key(c: Dict[str, Any]) -> Tuple[Tuple[int, ...], str]:
        vk = _version_sort_key(c.get("version"))
        rd = c.get("store_release_date") or ""
        return (vk, rd)

    return max(ok, key=key)


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

    def _strip_internal(self, d: Dict[str, Any]) -> Dict[str, Any]:
        out = {k: v for k, v in d.items() if not k.startswith("_")}
        return out

    async def _lookup_country_bundle(self, bundle_id: str, country: str) -> Dict[str, Any]:
        data = await self._make_request({"bundleId": bundle_id, "country": country})
        if "error" in data:
            return {"status": "error", "message": data["error"], "_country": country}
        if data.get("resultCount", 0) > 0:
            return _available_payload(data["results"][0], country)
        return {
            "status": "unavailable",
            "name": None,
            "version": None,
            "message": f"Приложение с Bundle ID '{bundle_id}' не найдено ({country})",
            "_country": country,
        }

    async def _lookup_country_id(self, app_id: int, country: str) -> Dict[str, Any]:
        data = await self._make_request({"id": app_id, "country": country})
        if "error" in data:
            return {"status": "error", "message": data["error"], "_country": country}
        if data.get("resultCount", 0) > 0:
            return _available_payload(data["results"][0], country)
        return {
            "status": "unavailable",
            "name": None,
            "version": None,
            "message": f"Приложение с ID '{app_id}' не найдено ({country})",
            "_country": country,
        }

    async def lookup_by_bundle_id(self, bundle_id: str) -> Dict[str, Any]:
        """
        Поиск по Bundle ID по нескольким витринам; выбирается ответ с максимальной версией.
        """
        countries = _parse_lookup_countries(settings.itunes_lookup_countries)
        try:
            parts = await asyncio.gather(
                *[self._lookup_country_bundle(bundle_id, c) for c in countries],
                return_exceptions=True,
            )
            candidates: List[Dict[str, Any]] = []
            errors: List[str] = []
            for i, p in enumerate(parts):
                cc = countries[i] if i < len(countries) else "?"
                if isinstance(p, BaseException):
                    logger.warning("lookup bundle %s country=%s: %s", bundle_id, cc, p)
                    errors.append(f"{cc}: {p}")
                    continue
                if p.get("status") == "error":
                    errors.append(f"{cc}: {p.get('message', 'error')}")
                candidates.append(p)

            available = [c for c in candidates if c.get("status") == "available"]
            if available:
                best = _pick_best_available(available)
                country = best.get("_country", "?")
                logger.info(
                    "iTunes bundle=%s → version=%s release_date=%s (витрина %s из %s)",
                    bundle_id,
                    best.get("version"),
                    best.get("store_release_date"),
                    country,
                    ",".join(countries),
                )
                return self._strip_internal(best)

            # Нет ни одной витрины с available
            unavail = [c for c in candidates if c.get("status") == "unavailable"]
            if unavail and len(unavail) == len(candidates):
                return {
                    "status": "unavailable",
                    "name": None,
                    "version": None,
                    "message": f"Приложение с Bundle ID '{bundle_id}' не найдено (витрины: {','.join(countries)})",
                }

            err_msg = errors[0] if errors else "Нет ответа от iTunes Lookup"
            return {
                "status": "error",
                "name": None,
                "version": None,
                "message": err_msg,
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
        """Поиск по App ID по нескольким витринам."""
        countries = _parse_lookup_countries(settings.itunes_lookup_countries)
        try:
            parts = await asyncio.gather(
                *[self._lookup_country_id(app_id, c) for c in countries],
                return_exceptions=True,
            )
            candidates: List[Dict[str, Any]] = []
            errors: List[str] = []
            for i, p in enumerate(parts):
                cc = countries[i] if i < len(countries) else "?"
                if isinstance(p, BaseException):
                    logger.warning("lookup id %s country=%s: %s", app_id, cc, p)
                    errors.append(f"{cc}: {p}")
                    continue
                if p.get("status") == "error":
                    errors.append(f"{cc}: {p.get('message', 'error')}")
                candidates.append(p)

            available = [c for c in candidates if c.get("status") == "available"]
            if available:
                best = _pick_best_available(available)
                country = best.get("_country", "?")
                logger.info(
                    "iTunes id=%s → version=%s release_date=%s (витрина %s из %s)",
                    app_id,
                    best.get("version"),
                    best.get("store_release_date"),
                    country,
                    ",".join(countries),
                )
                return self._strip_internal(best)

            unavail = [c for c in candidates if c.get("status") == "unavailable"]
            if unavail and len(unavail) == len(candidates):
                return {
                    "status": "unavailable",
                    "name": None,
                    "version": None,
                    "message": f"Приложение с ID '{app_id}' не найдено (витрины: {','.join(countries)})",
                }

            err_msg = errors[0] if errors else "Нет ответа от iTunes Lookup"
            return {
                "status": "error",
                "name": None,
                "version": None,
                "message": err_msg,
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
