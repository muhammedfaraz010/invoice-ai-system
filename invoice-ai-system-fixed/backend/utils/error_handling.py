import functools
import logging
import traceback
from typing import Any, Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ProcessingStageError(Exception):
    """Exception carrying a user-facing processing stage failure."""

    def __init__(self, stage: str, error: str, details: Optional[str] = None):
        self.stage = stage
        self.error = error
        self.details = details or error
        super().__init__(self.details)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": False,
            "stage": self.stage,
            "error": self.error,
            "details": self.details,
        }


def structured_error(stage: str, error: str, details: Optional[str] = None) -> dict[str, Any]:
    return {
        "success": False,
        "stage": stage,
        "error": error,
        "details": details or error,
    }


def log_stage(stage: str, user_error: Optional[str] = None) -> Callable:
    """Log a major processing stage and convert unexpected errors to stage errors."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            stage_logger = logging.getLogger(func.__module__)
            stage_logger.debug("[%s] Starting %s", stage, func.__qualname__)
            try:
                result = func(*args, **kwargs)
                stage_logger.debug("[%s] Finished %s", stage, func.__qualname__)
                return result
            except ProcessingStageError:
                raise
            except Exception as e:
                stage_logger.exception(e)
                traceback.print_exc()
                raise ProcessingStageError(stage, user_error or str(e), str(e)) from e

        return wrapper

    return decorator


async def processing_exception_middleware(request: Request, call_next):
    """Return structured JSON for any unhandled API exception."""

    try:
        return await call_next(request)
    except ProcessingStageError as e:
        logger.exception(e)
        traceback.print_exc()
        return JSONResponse(status_code=400, content=e.to_dict())
    except Exception as e:
        logger.exception(e)
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=structured_error("API", "Internal server error", str(e)),
        )
