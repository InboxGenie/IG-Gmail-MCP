from abc import ABC, abstractmethod
from typing import Any, Dict, List
from googleapiclient.discovery import build, Resource
from google.oauth2.credentials import Credentials
import os
import time
from datetime import datetime

client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
client_id = os.getenv("GOOGLE_CLIENT_ID")

type MCPDictListResponse = List[Dict[str, Any]]

class MCPAction(ABC):
    gmail_client: Resource

    def __init__(self, refresh_token: str):
        authorized_user_creds: Credentials = Credentials.from_authorized_user_info(self.__build_authorized_user_info(refresh_token))
        self.gmail_client = build("gmail", "v1", credentials=authorized_user_creds)

    @abstractmethod
    def execute[T](self, **kwargs: Any) -> T:
        pass

    def __build_authorized_user_info(refresh_token: str) -> dict:
        return {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }


class DeleteMessages(MCPAction):
    def __init__(self, refresh_token: str):
        super().__init__(refresh_token)


    def execute[int](self, **kwargs: Any) -> int:
        message_ids: list[str] = kwargs.get("message_ids", [])

        if not message_ids:
            return 0
        
        self.gmail_client.users().messages().batchDelete(userId="me", body={"ids": message_ids}).execute()

        return len(message_ids)
    

class GetUnreadMessages(MCPAction):
    def __init__(self, refresh_token: str):
        super().__init__(refresh_token)
    
    def execute[MCPDictListResponse](self, **kwargs: Any) -> MCPDictListResponse:
        _from: int = kwargs.get("from_date", self.__get_default_from_date())

        date: str = datetime.fromtimestamp(_from).strftime("%Y/%m/%d %H:%M:%S")
        gmail_response = self.gmail_client.users().messages().list(userId="me", q=f"is:unread after:{date}").execute()

        messages: list[dict] = gmail_response["messages"]
        
        for id, thread_id in messages:
            message = self.gmail_client.users().messages().get(userId="me", id=id, format="full").execute()
            print(message)


    def __get_default_from_date(self) -> int:
        return int(time.time()) - 5 * 24 * 60 * 60



        