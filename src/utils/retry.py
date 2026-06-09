"""Exponential backoff retry decorator."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries an async function with exponential backoff."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            "Attempt %d/%d for %s failed: %s. Retrying in %.1fs",
                            attempt + 1,
                            max_attempts,
                            func.__name__,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "All %d attempts for %s failed", max_attempts, func.__name__
                        )
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
