"""DynamoDB client"""

import json
import time
import os
from typing import List
import boto3
from boto3.dynamodb.conditions import Key, Attr

class DynamoDbClient():
    """DynamoDB client"""
    def __init__(self):
        self._messages_table_name = os.getenv("MESSAGES_TABLE_NAME")
        self._user_providers_table_name = os.getenv("USER_PROVIDERS_TABLE_NAME")
        self._cleanup_table_name = os.getenv("CLEAN_UP_TABLE_NAME")

    def get_messages(self, hash_key: str, sender: list[str] | None = None, _from: int | None = None, _to: int | None = None) -> list[dict]:
        """Get the messages from the DynamoDB table"""
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
        """Get the refresh token for the user"""
        client = boto3.resource("dynamodb")
        table = client.Table(self._user_providers_table_name)

        response = table.query(
            KeyConditionExpression=Key("email_hash").eq(hash_key) & Key("provider").eq("GMAIL"),
            IndexName="email_hash-provider-index"
        )

        refresh_tokens: List[str] = [json.loads(item["auth_details"])["refresh_token"] for item in response["Items"]]

        return refresh_tokens if len(refresh_tokens) > 1 else refresh_tokens[0] if refresh_tokens else None
    
    def get_message_item(self, email_hash: str, message_id: str) -> dict | None:
        """Get the message item from the DynamoDB table"""
        client = boto3.resource("dynamodb")
        table = client.Table(self._messages_table_name)

        response = table.get_item(
            Key={"email_hash": email_hash, "message_id": message_id},
            ProjectionExpression="message_body,message_from,message_to,message_subject,created_at_timestamp"
        )

        return response["Item"] if "Item" in response else None

    def get_user_messages_by_filter(self, email_hash: str, dynamo_db_filter: Attr, max_items: int = 100) -> list[dict]:
        """Get the user messages by filter"""
        items: list[dict] = []  

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(self._messages_table_name)
        response = table.query(
            KeyConditionExpression=Key('email_hash').eq(email_hash),
            FilterExpression=dynamo_db_filter or ""
        )
        items.extend(response['Items'])

        while response.get('LastEvaluatedKey'):
            if len(items) >= max_items:
                break

            response = table.query(
                KeyConditionExpression=Key('email_hash').eq(email_hash),
                FilterExpression=dynamo_db_filter,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response['Items'])

        return items

    def get_user_messages_by_message_id(self, email_hash: str, message_id: str) -> dict | None:
        """Get the user messages by message id"""
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(self._messages_table_name)
        response = table.get_item(Key={'email_hash': email_hash, 'message_id': message_id})
        return response['Item'] if 'Item' in response else None

    def add_vector_file_to_cleanup(self, file_name: str, file_id: str):
        """Add the vector file to the cleanup table so that it can be deleted after a certain time"""
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(self._cleanup_table_name)
        ttl_value = int(time.time()) + 600
        table.put_item(
            Item={
                "type": "vector_file",
                "details": json.dumps({"file_name": file_name, "file_id": file_id}),
                "delete_at": ttl_value
            }
        )
