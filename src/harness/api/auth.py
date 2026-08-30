import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from harness.config import get_settings
from harness.auth.revocation import is_revoked

_bearer = HTTPBearer(auto_error = True)

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer))->dict:
    setting = get_settings()
    try:
        payload = jwt.decode(
            creds.credentials, 
            setting.jwt_secret, 
            algorithms = [setting.jwt_algorithm],
        )
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    
    jti = payload.get("jti")
    if jti and await is_revoked(jti):
        raise HTTPEception(status.HTTP_401_UNAUTHORIZED, "token revoked")
    
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token missing subject")
    return {"user_id": user_id, "role": payload.get("role", "user")}

def require_admin(user: dict = Depends(get_current_user))->dict:
    if user.get("role")!= "admin":
        raise HTTPExeption(status.HTTP_403_UNAUTHORIZED, "admin access required")
    return user

