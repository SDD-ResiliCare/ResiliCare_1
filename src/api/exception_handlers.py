from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_request: Request, _exc: IntegrityError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "record conflicts with an existing value or relation"})
