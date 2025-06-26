import os


def get_session_store() -> str:
    session_store = os.getenv("MCP_SESSION_STATE_TABLE_NAME", None)

    if session_store is None:
        raise ValueError("SESSION_STORE is not set")
    
    return session_store

