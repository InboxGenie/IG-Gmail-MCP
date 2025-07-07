"""Gmail MCP actions"""

from abc import ABC, abstractmethod
import io
import json
import os
import time
from typing import Any, Dict, List
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials
from openai.types.vector_stores import VectorStoreFile
from boto3.dynamodb.conditions import Attr
#pylint: disable=E0611
from pinecone import QueryResponse
from mcp_server.encoders import DecimalEncoder
from mcp_server.dynamodb import DynamoDbClient
from mcp_server.typings import VectorStoreAttributes
from mcp_server.pinecone_client import PineconeClient
from mcp_server.reasoning_engine import ReasoningEngine
from mcp_server.models import QueryFilter
from mcp_server.open_ai_client import OpenAIClient
from mcp_server.internal_logger import InternalLogger

client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
client_id = os.getenv("GOOGLE_CLIENT_ID")


type MCPDictListResponse = List[Dict[str, Any]]

class MCPAction(ABC):
    """Base class for all MCP actions"""
    gmail_client: Resource

    def __init__(self, refresh_token: str | None = None):
        if refresh_token is None:
            return
        
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
        InternalLogger.LogDebug(f"Deleting messages {message_ids}")

        if not message_ids:
            return 0
        
        #pylint: disable=E1101
        self.gmail_client.users().messages().batchDelete(userId="me", body={"ids": message_ids}).execute()

        return len(message_ids)
    

class GetUnreadMessages(MCPAction):
    """Get unread messages from the user's inbox"""

    __openai_client: OpenAIClient = OpenAIClient()
    __dynamo_db_client: DynamoDbClient = DynamoDbClient()

    def execute[T](self, **kwargs: Any) -> T:
        from_date = kwargs.get("from_date")
        email_hash = kwargs.get("email_hash")

        InternalLogger.LogDebug(f"Getting unread messages from {from_date} for {email_hash}")

        assert email_hash is not None, "email_hash is required"

        _from: int = int(from_date) if from_date is not None else self.__get_default_from_date()

        InternalLogger.LogDebug(f"Getting unread messages from {_from}")

        #pylint: disable=E1101
        gmail_response = self.gmail_client.users().messages().list(userId="me", q=f"is:unread after:{_from}", maxResults=20).execute()

        messages: list[dict] = gmail_response["messages"] if "messages" in gmail_response else []
        unread_messages: list[dict] = []
        for message in messages:
            #pylint: disable=E1101
            message_item: dict | None = self.__dynamo_db_client.get_message_item(email_hash, message["id"])
            if message_item is None:
                InternalLogger.LogDebug(f"Message {message['id']} not found in DynamoDB")
                continue

            unread_messages.append(message_item)

        InternalLogger.LogDebug(f"Found {len(unread_messages)} unread messages")
        
        return unread_messages

    def upload_to_vector_store(self, unread_messages: list[dict], request_id: str):
        """Upload unread messages to the vector store"""

        vector_store_id: str = os.getenv("VECTOR_STORE_ID")
        assert vector_store_id is not None, "VECTOR_STORE_ID is not set"
        assert request_id is not None, "request_id is required"
        assert unread_messages is not None and len(unread_messages) > 0, "unread_messages is required"

        InternalLogger.LogDebug(f"Uploading {len(unread_messages)} unread messages to the vector store")

        InternalLogger.LogDebug("Creating file in OpenAI")
        file_id: str = self.__openai_client.upload_vector_store_file(
            file=(f"{request_id}.json", io.BytesIO(json.dumps(unread_messages, cls=DecimalEncoder).encode("utf-8")), "application/json"),
            purpose="user_data"
        ).id

        InternalLogger.LogDebug("File created in OpenAI")

        attributes: VectorStoreAttributes = {"request_id": request_id}

        InternalLogger.LogDebug("Creating vector store file in OpenAI")
        file_id: str = self.__openai_client.create_vector_store_file(
            vector_store_id=vector_store_id,
            file_id=file_id,
            attributes=attributes
        ).id

        InternalLogger.LogDebug(f"Vector store file created in OpenAI: {file_id}")

        self.wait_for_file_to_be_ready(file_id, vector_store_id)

    def wait_for_file_to_be_ready(self, file_id: str, vector_store_id: str):
        """Wait for the file to be ready"""

        InternalLogger.LogDebug(f"Waiting for file {file_id} to be ready in vector store {vector_store_id}")

        assert file_id is not None, "file_id is required"
        assert vector_store_id is not None, "vector_store_id is required"

        InternalLogger.LogDebug("Waiting for file to be ready")

        while True:
            file: VectorStoreFile = self.__openai_client.get_vector_store_file(vector_store_id=vector_store_id, file_id=file_id)
            if file.status == "completed":
                InternalLogger.LogDebug(f"File {file_id} is ready in vector store {vector_store_id}")
                break
            time.sleep(.5)

    def __get_default_from_date(self) -> int:
        return int(time.time()) - 5 * 24 * 60 * 60
    
class QueryMessages(GetUnreadMessages):
    """Query messages from the user's inbox"""
    __pinecone_client: PineconeClient
    __reasoning_engine: ReasoningEngine

    def __init__(self):
        self.__pinecone_client = PineconeClient()
        self.__reasoning_engine = ReasoningEngine()
        self.__dynamo_db_client = DynamoDbClient()
        super().__init__(None)

    def execute[T](self, **kwargs: Any) -> T:
        """Execute the action"""
        query_str: str = kwargs.get("query")
        email_hash: str = kwargs.get("email_hash")
        request_id: str = kwargs.get("request_id")

        InternalLogger.LogDebug(f"Querying messages for {query_str} for {email_hash} with request_id {request_id}")

        assert request_id is not None, "request_id is required"
        assert query_str is not None, "query_str is required"
        assert email_hash is not None, "email_hash is required"

        messages: List[dict] = self.query(email_hash, query_str, None)

        InternalLogger.LogDebug(f"Found {len(messages)} messages for {query_str} for {email_hash} with request_id {request_id}")

        self.upload_to_vector_store(messages, request_id)

        return messages

    def query(self, email_hash: str, query: str, ui_filter: QueryFilter | None) -> List[dict]:
        """Query the user's inbox for messages"""

        reasoning_filters: dict = self.__reasoning_engine.get_additional_filters(query)

        InternalLogger.LogDebug(f"Reasoning filters: {reasoning_filters}")

        is_filtering_by_date: bool = reasoning_filters.get("filtering_by_date", False)

        InternalLogger.LogDebug(f"Is filtering by date: {is_filtering_by_date}")

        if is_filtering_by_date:
            return self._process_date_related_query(email_hash, query, ui_filter, reasoning_filters)
        
        return  self._process_non_date_related_query(email_hash, query, ui_filter)


    def _process_date_related_query(self, email_hash: str, query: str, ui_filter: QueryFilter | None, reasoning_filters: dict) -> List[dict]:
        InternalLogger.LogDebug(f"Processing date related query for {query} for {email_hash}")

        dynamo_db_filter: Attr = self.__reasoning_engine.convert_pinecone_filter_to_dynamodb_filter(reasoning_filters, ui_filter)
        InternalLogger.LogDebug(f"DynamoDB filter: {dynamo_db_filter}")

        user_messages: list[dict] = self.__dynamo_db_client.get_user_messages_by_filter(email_hash, dynamo_db_filter)

        InternalLogger.LogDebug(f"Found {len(user_messages)} user messages for {query} for {email_hash}")

        filtered_user_messages: list[dict] = []
        if reasoning_filters.get("is_asking_about_specific_details", False):
            InternalLogger.LogDebug("Asking about specific details")

            filtered_user_messages: QueryResponse = self.__pinecone_client.search(
                "onboarding",
                email_hash,
                query,
                additional_filters=self._build_pinecone_filter(list(map(lambda x: x["message_id"], user_messages)), ui_filter),
                top_k=len(user_messages)
            )

            filtered_user_messages = [match.id for match in filtered_user_messages.matches]

            InternalLogger.LogDebug(f"Filtered user messages: {filtered_user_messages}")

        user_messages = [message for message in user_messages if message["message_id"] in filtered_user_messages] if len(filtered_user_messages) > 0 else user_messages

        InternalLogger.LogDebug(f"User messages: {user_messages}")

        return user_messages

    def _process_non_date_related_query(self, email_hash: str, query: str, ui_filter: QueryFilter | None) -> List[dict]:
        InternalLogger.LogDebug(f"Processing non date related query for {query} for {email_hash}")

        filtered_user_messages: QueryResponse = self.__pinecone_client.search("onboarding", email_hash, query, additional_filters=self._build_pinecone_filter([], ui_filter))
        vector_ids = [match.id for match in filtered_user_messages.matches]
        InternalLogger.LogDebug(f"Vector IDs: {vector_ids}")

        return  [self.__dynamo_db_client.get_user_messages_by_message_id(email_hash, vector_id) for vector_id in vector_ids]

    def _build_pinecone_filter(self, vector_ids: list[str], ui_filter: QueryFilter | None) -> dict:
        filter: dict = {}
        
        if len(vector_ids) > 0:
            filter["vector_id"] = {"$in": vector_ids}

        if not ui_filter:
            return filter
        
        if ui_filter.inboxes:
            filter["provider"] = {"$in": ui_filter.inboxes}

        if ui_filter.recipients:
            filter["to"] = {"$in": ui_filter.recipients}

        if ui_filter.from_email:
            filter["from"] = {"$in": ui_filter.from_email}

        if ui_filter.start_date:
            filter["date"] = {"$gte": ui_filter.start_date_timestamp()}

        if ui_filter.end_date:
            filter["date"] = {"$lte": ui_filter.end_date_timestamp()}

        return filter