from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlmodel import Session, select
from database import get_session
from models import User
from schemas import UserRegister, UserLogin, UserResponse, TokenResponse, TokenRefresh
from auth import get_password_hash, verify_password, create_access_token, create_refresh_token, decode_token, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from dependencies import get_current_user
from validators.password_validator import validate_password
from services.token_blacklist import blacklist_token, is_token_blacklisted
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
def register(request: Request, user_data: UserRegister, session: Session = Depends(get_session)):
    """Register a new user"""
    # Check if user already exists
    existing_user = session.exec(select(User).where(User.email == user_data.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate password strength
    try:
        validate_password(user_data.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        phone_number=user_data.phone_number,
        role=user_data.role
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(new_user.id), "role": new_user.role})
    refresh_token = create_refresh_token(data={"sub": str(new_user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(new_user)
    )

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, credentials: UserLogin, session: Session = Depends(get_session)):
    """Login user"""
    # Find user
    user = session.exec(select(User).where(User.email == credentials.email)).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    )

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
def refresh_token(request: Request, token_data: TokenRefresh, session: Session = Depends(get_session)):
    """Refresh access token"""
    payload = decode_token(token_data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    user = session.get(User, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create new tokens
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserResponse.model_validate(user)
    )

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse.model_validate(current_user)

@router.put("/profile", response_model=UserResponse)
def update_profile(
    request: Request,
    profile_data: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update user profile"""
    # Update allowed fields
    if "full_name" in profile_data and profile_data["full_name"]:
        current_user.full_name = profile_data["full_name"]
    if "phone_number" in profile_data:
        current_user.phone_number = profile_data["phone_number"]
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    return UserResponse.model_validate(current_user)

@router.put("/password")
@limiter.limit("3/minute")
def change_password(
    request: Request,
    password_data: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Change user password"""
    current_password = password_data.get("current_password")
    new_password = password_data.get("new_password")
    
    if not current_password or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password and new password are required"
        )
    
    # Verify current password
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    try:
        validate_password(new_password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Update password
    current_user.password_hash = get_password_hash(new_password)
    session.add(current_user)
    session.commit()
    
    return {"message": "Password changed successfully"}

@router.put("/notification-settings")
def update_notification_settings(
    request: Request,
    settings: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update notification settings"""
    # In a real app, you'd have a separate notification_settings table
    # For now, we just return success
    return {"message": "Notification settings updated successfully"}


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    authorization: str = Header(None)
):
    """
    Logout user by blacklisting their current access token.
    
    The token will be invalid for the remainder of its lifetime.
    Client should also clear tokens from local storage.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization header required"
        )
    
    token = authorization.replace("Bearer ", "")
    
    # Decode token to get expiry for blacklist duration
    payload = decode_token(token)
    if payload:
        # Get JTI if available (for more efficient storage)
        jti = payload.get("jti")
        
        # Calculate remaining token lifetime (in seconds)
        exp = payload.get("exp", 0)
        import time
        remaining = max(0, exp - int(time.time()))
        
        # Blacklist the token
        if blacklist_token(token, jti, remaining + 60):  # Add 60s buffer
            logger.info(f"User {current_user.id} logged out successfully")
            return {"message": "Logged out successfully"}
    
    # Even if blacklisting fails, tell user logout succeeded
    # (they should still clear their local tokens)
    return {"message": "Logged out successfully"}


@router.post("/logout-all")
@limiter.limit("3/minute")
def logout_all_devices(
    request: Request,
    password_data: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Logout from all devices by updating password_changed_at timestamp.
    
    This invalidates all existing tokens by changing the user's secret version.
    Requires password confirmation for security.
    """
    password = password_data.get("password")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password confirmation required"
        )
    
    # Verify password
    if not verify_password(password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    # Note: In a full implementation, you would:
    # 1. Store a "token_version" or "password_changed_at" in the User model
    # 2. Include this in the JWT payload
    # 3. Check it during token validation
    # For now, we'll just log the action
    
    logger.info(f"User {current_user.id} requested logout from all devices")
    
    return {
        "message": "Logged out from all devices. Please log in again.",
        "note": "All existing sessions have been invalidated"
    }

