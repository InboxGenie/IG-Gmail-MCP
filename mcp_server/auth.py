"""Authentication module for the MCP server."""

import os
import jwt
from fastmcp.exceptions import ValidationError

JWT_SECRET = os.getenv("SECRET_KEY", None)

def get_auth(event: dict) -> tuple[str, str]:
    """
    Get the authorized user from the event.
    """

    headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
    token = headers.get("authorization", None)
    request_id = headers.get("request_id", None)

    assert request_id is not None, "Request ID is required"

    if not token:
        raise ValidationError("Authorization header is required")

    valid, token = validate_token(token)

    if not valid:
        raise ValidationError("Invalid token")

    return token, request_id

def validate_token(token: str) -> tuple[bool, dict]:
    """
    Validate the token.
    """

    if not JWT_SECRET:
        raise ValidationError("SECRET_KEY is not set")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return False, {}
    except jwt.InvalidTokenError:
        return False, {}

    return True, payload