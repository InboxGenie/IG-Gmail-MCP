"""Gmail MCP actions"""

from abc import ABC, abstractmethod
import base64
import email
import io
import json
import os
import time
from typing import Any, Dict, List
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials


from openai import OpenAI

from mcp_server.typings import VectorStoreAttributes

client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
client_id = os.getenv("GOOGLE_CLIENT_ID")


type MCPDictListResponse = List[Dict[str, Any]]

class MCPAction(ABC):
    """Base class for all MCP actions"""
    gmail_client: Resource

    def __init__(self, refresh_token: str):
        authorized_user_creds: Credentials = Credentials.from_authorized_user_info(self.__build_authorized_user_info(refresh_token))
        self.gmail_client = build("gmail", "v1", credentials=authorized_user_creds)

    @abstractmethod
    def execute[T](self, **kwargs: Any) -> T:
        """Execute the action"""

    def __build_authorized_user_info(self, refresh_token: str) -> dict:
        return {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }


class DeleteMessages(MCPAction):
    """Delete messages from the user's inbox"""

    def execute[T](self, **kwargs: Any) -> T:
        message_ids: list[str] = kwargs.get("message_ids", [])

        if not message_ids:
            return 0
        
        #pylint: disable=E1101
        self.gmail_client.users().messages().batchDelete(userId="me", body={"ids": message_ids}).execute()

        return len(message_ids)
    

class GetUnreadMessages(MCPAction):
    """Get unread messages from the user's inbox"""

    def execute[T](self, **kwargs: Any) -> T:
        from_date = kwargs.get("from_date")
        request_id: str = kwargs.get("request_id")

        assert request_id is not None, "request_id is required"

        _from: int = int(from_date) if from_date is not None else self.__get_default_from_date()

        #pylint: disable=E1101
        gmail_response = self.gmail_client.users().messages().list(userId="me", q=f"is:unread after:{_from}").execute()

        messages: list[dict] = gmail_response["messages"] if "messages" in gmail_response else []
        unread_messages: list[str] = []
        for message in messages:
            #pylint: disable=E1101
            message_response = self.gmail_client.users().messages().get(userId="me", id=message["id"], format="raw").execute()
            message_content = base64.urlsafe_b64decode(message_response["raw"].encode("ASCII"))
            message_content = email.message_from_bytes(message_content)
            unread_messages.append(message_content.as_string())

        if unread_messages:
            self.upload_to_vector_store(unread_messages, request_id)
        
        return len(unread_messages)

    def upload_to_vector_store(self, unread_messages: list[str], request_id: str):
        """Upload unread messages to the vector store"""

        vector_store_id: str = os.getenv("VECTOR_STORE_ID")
        assert vector_store_id is not None, "VECTOR_STORE_ID is not set"
        assert request_id is not None, "request_id is required"
        assert unread_messages is not None and len(unread_messages) > 0, "unread_messages is required"

        openai_client: OpenAI = OpenAI()

        file_id: str = openai_client.files.create(
            file=io.BytesIO(json.dumps(unread_messages).encode("utf-8")),
            purpose="user_data"
        ).id

        attributes: VectorStoreAttributes = {"request_id": request_id}

        openai_client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_id,
            attributes=attributes
        )

    def __get_default_from_date(self) -> int:
        return int(time.time()) - 5 * 24 * 60 * 60