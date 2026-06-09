"""Exponential backoff retry decorator with HTTP status awareness."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# HTTP status codes that should NOT be retried
_NON_RETRYABLE_STATUS_CODES = frozenset({400, 401, 403, 404, 405, 409, 422})


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is worth retrying."""
    try:
        import httpx

        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status in _NON_RETRYABLE_STATUS_CODES:
                return False
            # Retry 429 (rate limit) and 5xx (server errors)
            return status == 429 or status >= 500
    except ImportError:
        pass
    # For non-HTTP exceptions (transport errors, etc.), always retry
    return True


def _get_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After delay from a 429 response, if present."""
    try:
        import httpx

        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
            retry_after = exc.response.headers.get("retry-after")
            if retry_after:
                return float(retry_after)
    except (ImportError, ValueError):
        pass
    return None


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries an async function with exponential backoff.

    Fails fast on 4xx client errors (401, 403, 404, etc.) with a clear message.
    Retries on 5xx server errors, 429 rate limits (honoring Retry-After), and
    transport errors.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc

                    # Fail fast on non-retryable errors
                    if not _is_retryable(exc):
                        logger.error(
                            "Non-retryable error in %s: %s", func.__name__, exc
                        )
                        raise

                    if attempt < max_attempts - 1:
                        # Honor Retry-After header for 429s
                        retry_after = _get_retry_after(exc)
                        delay = retry_after or min(
                            base_delay * (2**attempt), max_delay
                        )
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
                            "All %d attempts for %s failed",
                            max_attempts,
                            func.__name__,
                        )
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
