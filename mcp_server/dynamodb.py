import json
from typing import List
import boto3
import os
from boto3.dynamodb.conditions import Key, Attr

class DynamoDbClient():
    def __init__(self):
        self._messages_table_name = os.getenv("MESSAGES_TABLE_NAME")
        self._user_providers_table_name = os.getenv("USER_PROVIDERS_TABLE_NAME")

    def get_messages(self, hash_key: str, sender: list[str] | None = None, _from: int | None = None, _to: int | None = None) -> list[dict]:
        client = boto3.resource("dynamodb")
        table = client.Table(self._messages_table_name)

        if sender:
            filter_expression = Attr("message_from").eq(sender[0])
            for sender in sender[1:]:
                filter_expression = filter_expression | Attr("message_from").eq(sender)
        else:
            filter_expression = None

        if _from:
            if filter_expression:
                filter_expression = filter_expression & Attr("created_at_timestamp").gte(_from)
            else:
                filter_expression = Attr("created_at_timestamp").gte(_from)
        if _to:
            if filter_expression:
                filter_expression = filter_expression & Attr("created_at_timestamp").lte(_to)
            else:
                filter_expression = Attr("created_at_timestamp").lte(_to)

        items: list[dict] = []
        
        response = table.query(
            KeyConditionExpression=Key("email_hash ").eq(hash_key),
            FilterExpression=filter_expression,
            ScanIndexForward=False,
            Limit=100
        )

        items.extend(response["Items"])

        while "LastEvaluatedKey" in response:
            response = table.query(
                KeyConditionExpression=Key("email_hash ").eq(hash_key),
                FilterExpression=filter_expression,
                ScanIndexForward=False,
                Limit=100,
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response["Items"])

        return items
    
    def get_refresh_token(self, hash_key: str) -> List[str] | str | None:
        client = boto3.resource("dynamodb")
        table = client.Table(self._user_providers_table_name)

        response = table.query(
            KeyConditionExpression=Key("email_hash").eq(hash_key) & Key("provider").eq("GMAIL"),
            IndexName="email_hash-provider-index"
        )

        refresh_tokens: List[str] = [json.loads(item["auth_details"])["refresh_token"] for item in response["Items"]]

        return refresh_tokens if len(refresh_tokens) > 1 else refresh_tokens[0] if refresh_tokens else None