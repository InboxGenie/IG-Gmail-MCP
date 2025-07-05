"""OpenAI API client"""

import os
from datetime import datetime
import uuid
import io
from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionChunk
from openai.types.responses import ResponseStreamEvent
from openai.types.vector_stores import VectorStoreFile

class OpenAIClient:
    """OpenAI API client"""
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def create_embedding(self, text: str) -> list[float]:
        """Create embedding from text"""
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
    
    def get_answer(self, context: str, query: str) -> str | Stream[ChatCompletionChunk]:
        """Get answer from OpenAI API"""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "developer", "content": context}, {"role": "user", "content": query}],
        )

        return response.choices[0].message.content

    def upload_vector_store_file(self, file: tuple[str, io.BytesIO, str], purpose: str) -> VectorStoreFile:
        """Upload a vector store file to OpenAI"""
        return self.client.files.create(file=file, purpose=purpose)

    def get_vector_store_file(self, vector_store_id: str, file_id: str) -> VectorStoreFile:
        """Get a vector store file from OpenAI"""
        return self.client.vector_stores.files.retrieve(vector_store_id=vector_store_id, file_id=file_id)

    def create_vector_store_file(self, vector_store_id: str, file_id: str, attributes: dict) -> VectorStoreFile:
        """Create a vector store file in OpenAI"""
        return self.client.vector_stores.files.create(vector_store_id=vector_store_id, file_id=file_id, attributes=attributes)

    def _get_prompt(self, today: str, timestamp: float) -> str:
        return f"""
            Use the provided mcp tools to answer the user's question.
            If you need to use the mcp tools, use the mcp tools to answer the user's question.
            If you don't need to use the mcp tools, answer the user's question directly.
            Today's date is {today}.
            The current timestamp is {str(timestamp)}.
            Always use the current date as reference if the user's question is mentioning the date in the past.
            Always use full day context unless the user's question is mentioning the time.
            So for example if the user's question is "What is the weather in Tokyo today?", you should use the full day context by converting the current timestamp to timestamp of the beginning of the day.
            But if the user's question is "What is the weather in Tokyo at 10:00 AM?", you should use the time context.
        """
