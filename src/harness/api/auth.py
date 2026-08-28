import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from harness.config import get_settings

_bearer = HTTPBearer(auto_error = True)

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer))->dict:
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
    
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token missing subject")
    return {"user_id": user_id, "role": payload.get("role", "user")}