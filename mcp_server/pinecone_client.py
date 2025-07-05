"""
Pinecone client
"""

from pinecone import Pinecone, QueryResponse
from mcp_server.open_ai_client import OpenAIClient

class PineconeClient:
    """Pinecone client"""

    __openai_client: OpenAIClient
    __client: Pinecone
    def __init__(self):
        self.__openai_client = OpenAIClient()
        self.__client = Pinecone()

    def get_index(self, index_name: str):
        """Get the index"""
        return self.__client.Index(index_name)

    def search(self, index_name: str, namespace: str, query: str, top_k: int = 10, additional_filters: dict = {}) -> QueryResponse:
        """Search the index"""
        index = self.get_index(index_name)
        embedded_query = self.__openai_client.create_embedding(query)
        return index.query(namespace=namespace, vector=embedded_query, top_k=top_k, filter=additional_filters)
    
    def delete_message_by_id(self, index_name: str, namespace: str, message_id: str):
        """Delete a message by id"""
        index = self.get_index(index_name)
        index.delete(namespace=namespace, ids=[message_id])