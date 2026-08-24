from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import create_access_token, get_current_user, hash_password, verify_password


router = APIRouter(prefix="/api/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str


class AuthUser(BaseModel):
    id: int
    username: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class RegistrationStatus(BaseModel):
    available: bool


def _auth_response(user: User) -> LoginResponse:
    return LoginResponse(
        access_token=create_access_token(user),
        user=AuthUser(id=user.id, username=user.username, role=user.role or "user"),
    )


@router.get("/registration-status", response_model=RegistrationStatus)
def registration_status(db: Session = Depends(get_db)):
    """Publicly expose only whether first-user initialization is available."""
    return RegistrationStatus(available=db.query(User.id).first() is None)


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Create the first administrator on a completely empty installation.

    Public self-registration closes as soon as one user exists. Further users
    must be created by an administrator through user management.
    """
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail={"message": "用户名不能为空"})
    if not payload.password:
        raise HTTPException(status_code=400, detail={"message": "密码不能为空"})
    if db.query(User.id).first() is not None:
        raise HTTPException(
            status_code=403,
            detail={"message": "系统已完成初始化，请联系管理员创建账号"},
        )

    user = User(username=username, password=hash_password(payload.password), role="admin")
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"message": "初始化账号已被创建，请直接登录"},
        ) from exc
    return _auth_response(user)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username.strip()).first()
    valid, needs_rehash = verify_password(payload.password, user.password if user else "")
    if user is None or not valid:
        raise HTTPException(status_code=401, detail={"message": "用户名或密码错误"})
    if needs_rehash:
        user.password = hash_password(payload.password)
        db.commit()
        db.refresh(user)
    return _auth_response(user)


@router.get("/me", response_model=AuthUser)
def me(current_user: User = Depends(get_current_user)):
    return AuthUser(id=current_user.id, username=current_user.username, role=current_user.role or "user")
