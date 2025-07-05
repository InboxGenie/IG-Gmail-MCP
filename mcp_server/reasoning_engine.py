"""
Reasoning engine
"""

from datetime import datetime
import json
import os
from typing import Literal

from openai import OpenAI
import dateutil.parser
from mcp_server.models import QueryFilter
from mcp_server.open_ai_client import OpenAIClient

from boto3.dynamodb.conditions import Key, Attr

REASONING_PROMPT_PINECONE = os.getenv("REASONING_PROMPT_PINECONE")

pinecone_filter_valid_strings = Literal["$lte", "$gte", "$eq", "$ne", "$gt", "$lt"]
pinecone_to_dynamodb_mapping: dict = {
    "$lte": "lte",
    "$gte": "gte",
    "$eq": "eq",
    "$ne": "ne",
    "$gt": "gt",
    "$lt": "lt"
}

local_secondary_index_column_name = "created_at_timestamp"

class ReasoningEngine:
    """Reasoning engine"""

    __openai_client: OpenAIClient

    def __init__(self):
        self.__openai_client = OpenAIClient()

    def get_additional_filters(self, user_input: str) -> list[str]:
        """Get additional filters"""
        user_input = user_input + " Current date: " + datetime.now().strftime("%d/%m/%Y %H:%M")
        response: str = self.__openai_client.get_answer(REASONING_PROMPT_PINECONE, user_input)

        converted_response: dict = self.__parse_response(response)
        valid: bool = self.__validate_response(converted_response)
        return self.__convert_to_timestamp(converted_response) if valid else {}

    def __parse_response(self, response: str) -> list[str]:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            print(f"Error parsing response: {response}")
            return {}
    
    def __validate_response(self, response: dict) -> bool:
        has_date = "date" in response
        is_dict = isinstance(response.get("date"), dict)
        valid_keys = all(key in pinecone_filter_valid_strings.__args__ for key in response.get("date", {}).keys())
        return has_date and is_dict and valid_keys
    
    def __convert_to_timestamp(self, response: dict) -> list[str]:
        for date_str in response.get("date", {}).keys():
            _value = response.get("date", {})[date_str]
            _date = dateutil.parser.parse(_value, dayfirst=True)
            response.get("date", {})[date_str] = int(_date.timestamp())

        return response
    
    @staticmethod
    def convert_pinecone_filter_to_dynamodb_filter(filter: dict | None, ui_filter: QueryFilter | None = None) -> Attr | None:
        """Convert Pinecone filter to DynamoDB filter"""
        if not filter and not ui_filter:
            return None
        
        date_relative_filter: Attr | None = None
        is_ui_filtering_by_date: bool = ui_filter and (ui_filter.start_date or ui_filter.end_date)

        # Handle reasoning filter if not filtering by date explicitly from UI
        if filter and 'date' in filter and not is_ui_filtering_by_date:
            date_filters = filter['date']
            gte = date_filters.get('$gte', None)
            lte = date_filters.get('$lte', int(datetime.now().timestamp()))
            
            if all([gte, lte]):
                date_relative_filter = Attr(local_secondary_index_column_name).between(gte, lte)

        # Handle UI filter
        if ui_filter:
            ui_dynamo_filter = PineconeFilterConverter.convert_ui_filter_to_dynamodb_filter(ui_filter, is_ui_filtering_by_date)
            if ui_dynamo_filter:
                if date_relative_filter:
                    date_relative_filter = date_relative_filter & ui_dynamo_filter
                else:
                    date_relative_filter = ui_dynamo_filter

        return date_relative_filter

class PineconeFilterConverter:
    @staticmethod
    def convert_ui_filter_to_dynamodb_filter(ui_filter: QueryFilter, is_ui_filtering_by_date: bool) -> Attr | None:
        ddb_filter: Attr | None = None

        if ui_filter.inboxes and len(list(filter(lambda x: x != "ALL", ui_filter.inboxes))) > 0:
            if ddb_filter:
                ddb_filter = ddb_filter & Attr("provided_key").contains(ui_filter.inboxes)
            else:
                ddb_filter = Attr("provided_key").contains(ui_filter.inboxes)

        if ui_filter.start_date and ui_filter.end_date and is_ui_filtering_by_date:
            if ddb_filter:
                ddb_filter = ddb_filter & Attr("created_at_timestamp").between(ui_filter.start_date_timestamp(), ui_filter.end_date_timestamp())
            else:
                ddb_filter = Attr("created_at_timestamp").between(ui_filter.start_date_timestamp(), ui_filter.end_date_timestamp())
        else:
            if ui_filter.start_date and is_ui_filtering_by_date:
                if ddb_filter:
                    ddb_filter = ddb_filter & Attr("created_at_timestamp").gte(ui_filter.start_date_timestamp())
                else:
                    ddb_filter = Attr("created_at_timestamp").gte(ui_filter.start_date_timestamp())

            if ui_filter.end_date and is_ui_filtering_by_date:
                if ddb_filter:
                    ddb_filter = ddb_filter & Attr("created_at_timestamp").lte(ui_filter.end_date_timestamp())
                else:
                    ddb_filter = Attr("created_at_timestamp").lte(ui_filter.end_date_timestamp())

        return ddb_filter