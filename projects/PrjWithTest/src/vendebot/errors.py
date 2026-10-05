"""Contrato unico de error de la API: {"error": {"code", "message", "trace_id"}}."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class VendeBotError(Exception):
    code = "VALIDATION_ERROR"
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ValidationError(VendeBotError):
    code = "VALIDATION_ERROR"
    status_code = 400


class UnauthorizedError(VendeBotError):
    code = "UNAUTHORIZED"
    status_code = 401


class NotFoundError(VendeBotError):
    code = "NOT_FOUND"
    status_code = 404


class OutOfStockError(VendeBotError):
    code = "OUT_OF_STOCK"
    status_code = 409


class ProposalExpiredError(VendeBotError):
    code = "PROPOSAL_EXPIRED"
    status_code = 409


class LLMUnavailableError(VendeBotError):
    code = "LLM_UNAVAILABLE"
    status_code = 503


class LLMInvalidOutputError(VendeBotError):
    code = "LLM_INVALID_OUTPUT"
    status_code = 502


class BudgetExceededError(VendeBotError):
    code = "BUDGET_EXCEEDED"
    status_code = 429


# No forma parte de los codigos minimos pedidos, pero evita disfrazar un 500
# real como VALIDATION_ERROR cuando no hay nada que el cliente pueda corregir.
class InternalError(VendeBotError):
    code = "INTERNAL_ERROR"
    status_code = 500


def error_body(code: str, message: str, trace_id: str | None) -> dict:
    return {"error": {"code": code, "message": message, "trace_id": trace_id}}


async def vendebot_error_handler(request: Request, exc: VendeBotError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, trace_id))


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    message = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
    return JSONResponse(status_code=400, content=error_body("VALIDATION_ERROR", message, trace_id))


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_ERROR", "Error interno inesperado", trace_id),
    )


def register_error_handlers(app) -> None:
    app.add_exception_handler(VendeBotError, vendebot_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
