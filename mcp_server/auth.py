from fastmcp.server.dependencies import get_http_headers
from fastmcp.exceptions import ValidationError
import os
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "SECRET_KEY")

def get_auth() -> dict:
    headers = get_http_headers()

    token = headers.get("Authorization", None)

    if not token:
        raise ValidationError("Authorization header is required")

    valid, token = validate_token(token)

    if not valid:
        raise ValidationError("Invalid token")

    return token

def validate_token(token: str) -> tuple[bool, dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return False, {}
    except jwt.InvalidTokenError:
        return False, {}

    return True, payload