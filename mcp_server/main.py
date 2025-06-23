from typing import Dict, Literal
from fastmcp import FastMCP
from mangum import Mangum

from mcp_server.auth import get_auth
from mcp_server.dynamodb import DynamoDbClient
from mcp_server.gmail_mcp_actions import DeleteMessages, GetUnreadMessages, MCPAction

mcp = FastMCP(
    name="ig-gmail-mcp",
    version="0.1.0",
    description="Gmail MCP Server",
    stateless_http=True,
    json_response=True
)

TypedMCPAction = Literal["delete_messages", "get_unread_messages"]

mcp_actions: Dict[TypedMCPAction, MCPAction] = {
    "delete_messages": DeleteMessages,
    "get_unread_messages": GetUnreadMessages
}

@mcp.tool(name="delete_messages", description="Delete messages from a single or multiple senders or from a specific date")
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
    auth: dict = get_auth()

    messages: list[dict] = DynamoDbClient.get_messages(sender, from_date, to_date)

    action_executor: MCPAction = mcp_actions["delete_messages"](auth["refresh_token"])

    return action_executor.execute(message_ids=[message["message_id"] for message in messages])


@mcp.tool(name="get_unread_messages", description="Get unread messages from a single or multiple senders or from a specific date")
def get_unread_messages_tool(from_date: int | None = None):
    """
    from_date: int | None = The date to get unread messages from. Should be a unix timestamp in utc.

    Returns the list of unread messages.
    """

    auth: dict = get_auth()

    action_executor: MCPAction = mcp_actions["get_unread_messages"](auth["refresh_token"])

    return action_executor.execute(from_date=from_date)


http_app = mcp.http_app()

def handler(event: dict, context: dict):
    mangum_handler = Mangum(http_app)
    return mangum_handler(event, context)


# if __name__ == "__main__":
#     uvicorn.run(http_app, host="0.0.0.0", port=8000)