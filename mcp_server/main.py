"""MCP server for Gmail integration with vector store capabilities."""

from typing import Dict, List, Literal

from awslabs.mcp_lambda_handler import MCPLambdaHandler
from mcp_server.auth import get_auth
from mcp_server.dynamodb import DynamoDbClient
from mcp_server.gmail_mcp_actions import DeleteMessages, GetUnreadMessages, MCPAction
from mcp_server.session_store import get_session_store


mcp = MCPLambdaHandler(name="ig-gmail-mcp", version="0.1.0", session_store=get_session_store())

TypedMCPAction = Literal["delete_messages", "get_unread_messages"]

mcp_actions: Dict[TypedMCPAction, MCPAction] = {
    "delete_messages": DeleteMessages,
    "get_unread_messages": GetUnreadMessages
}

authorized_user: dict | None = None
request_id: str | None = None

@mcp.tool()
def delete_messages_tool(sender: list[str] | None = None, from_date: int | None = None, to_date: int | None = None):
    """
    sender: list[str] = The list of senders to delete messages from. Has to be a list of valid email addresses.
    from_date: int | None = The date to delete messages from. Should be a unix timestamp in utc.
    to_date: int | None = The date to delete messages to. Should be a unix timestamp in utc.
    
    If sender is provided, all messages from the sender will be deleted.
    If from_date is provided, all messages from the date will be deleted.

    If both are provided, all messages from the sender on the date will be deleted.

    Returns the number of messages deleted.
    """
    messages: list[dict] = DynamoDbClient().get_messages(authorized_user["email_hash"], sender, from_date, to_date)

    action_executor: MCPAction = mcp_actions["delete_messages"](authorized_user["refresh_token"])

    return action_executor.execute(message_ids=[message["message_id"] for message in messages])


@mcp.tool()
def get_unread_messages_tool(from_date: int | None = None):
    """
    from_date: int | None = The date to get unread messages from. Should be a unix timestamp in utc.

    inbox: str | None = The inbox to get unread messages from. Should be a valid email address or empty string to get all inboxes.

    Saves the unread messages to the vector store and model should call the file_search tool to get the messages.

    Returns the number of unread messages. If it's 0, it means no unread messages were found if it's greater than 0, it means unread messages were found and the model should call the file_search tool to get the messages.
    """

    refresh_tokens: str | List[str] | None = DynamoDbClient().get_refresh_token(authorized_user["email_hash"])
    if isinstance(refresh_tokens, list):
        unread_messages: List[str] = []
        for refresh_token in refresh_tokens:
            action_executor: MCPAction = mcp_actions["get_unread_messages"](refresh_token)
            unread_messages.extend(action_executor.execute(from_date=from_date, email_hash=authorized_user["email_hash"]))
    
    if isinstance(refresh_tokens, str):
        action_executor: MCPAction = mcp_actions["get_unread_messages"](refresh_tokens)
        unread_messages: List[str] = action_executor.execute(from_date=from_date, email_hash=authorized_user["email_hash"])

    if len(unread_messages) > 0:
        action_executor.upload_to_vector_store(unread_messages, request_id)


    return "Now use file_search tool to retrieve the messages. The file contains the unread messages." if len(unread_messages) > 0 else "No unread messages found"

def handler(event, context):
    """
    Handler for the MCP server.
    """

    #pylint: disable=W0603
    global authorized_user
    global request_id

    authorized_user, request_id = get_auth(event)
    return mcp.handle_request(event, context)
