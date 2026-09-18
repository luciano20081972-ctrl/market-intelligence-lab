from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.exc import SQLAlchemyError

from apps.api.dependencies import get_principal
from packages.auth import AuthError, AuthPrincipal, native

router = APIRouter(prefix="/auth", tags=["native authentication"])


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    login: str = Field(min_length=3, max_length=160)
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=15, max_length=128)


def native_only(request: Request) -> None:
    if request.app.state.settings.auth_mode != "native":
        raise HTTPException(404, "Not found")


def source(request: Request) -> str:
    # Never trust caller-supplied X-Forwarded-For. Behind the existing proxy all
    # callers share its conservative source budget; account/global limits remain.
    return request.client.host if request.client else "unknown"


@router.post("/login", dependencies=[Depends(native_only)])
def sign_in(payload: LoginPayload, request: Request) -> dict[str, str]:
    state = request.app.state
    token = native.login(
        state.session_factory,
        state.engine,
        state.settings,
        payload.login,
        payload.password.get_secret_value(),
        source(request),
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=204, dependencies=[Depends(native_only)])
def sign_out(request: Request, principal: AuthPrincipal = Depends(get_principal)) -> Response:
    native.logout(request.app.state.session_factory, principal)
    return Response(status_code=204)


@router.post("/password", status_code=204, dependencies=[Depends(native_only)])
def change_password(
    payload: PasswordPayload,
    request: Request,
    principal: AuthPrincipal = Depends(get_principal),
) -> Response:
    state = request.app.state
    native.change_password(
        state.session_factory,
        state.engine,
        state.settings,
        principal,
        payload.current_password.get_secret_value(),
        payload.new_password.get_secret_value(),
        source(request),
    )
    return Response(status_code=204)


def public_error(exc: Exception) -> HTTPException:
    if isinstance(exc, native.AuthBusy):
        return HTTPException(
            429, "Authentication temporarily limited", headers={"Retry-After": "60"}
        )
    if isinstance(exc, AuthError):
        return HTTPException(401, "Invalid credentials or session")
    if isinstance(exc, SQLAlchemyError):
        return HTTPException(503, "Authentication unavailable")
    return HTTPException(503, "Authentication unavailable")
