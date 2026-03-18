from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from api.auth import create_access_token
from api.deps import get_current_user
from api.models import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from core.domain.user import User
from core.exceptions import InvalidInputError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    try:
        user = await User.create(
            username=request.username,
            email=request.email,
            password=request.password,
        )
        token = create_access_token(data={"sub": user.id})
        return TokenResponse(access_token=token)
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user = await User.get_by_username(request.username)
    if not user or not User.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(data={"sub": user.id})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        created=current_user.created,
    )
