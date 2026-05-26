from datetime import datetime
from typing import Optional
from database.core import Core


class BatchTasksDB(Core):
    """Database class for managing batch progress and tasks"""

    def __init__(self, uri, database_name):
        super().__init__(uri, database_name, "batch_tasks")

    async def create_task(self, doc_data: dict) -> int:
        """Create a new batch task in the database"""
        doc = {
            "_id": doc_data["task_id"],
            "user_id": int(doc_data["user_id"]),
            "source_chat_id": int(doc_data["source_chat_id"]),
            "source_chat_title": doc_data.get("source_chat_title", "Chat"),
            "first_message_id": int(doc_data["first_message_id"]),
            "last_message_id": int(doc_data["last_message_id"]),
            "current_message_id": int(doc_data["first_message_id"]),
            "total_messages": int(doc_data["total_messages"]),
            "processed_count": 0,
            "status": "running",
            "notion_enabled": bool(doc_data.get("notion_enabled", False)),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        return await super().create(doc)

    async def update_progress(self, task_id: int, current_message_id: int, processed_count: int):
        """Update current message and processed count of a task"""
        update_data = {
            "current_message_id": current_message_id,
            "processed_count": processed_count,
            "updated_at": datetime.now(),
        }
        return await super().update(task_id, update_data)

    async def update_status(self, task_id: int, status: str, processed_count: int = None):
        """Update status and optionally processed count of the task"""
        update_data = {
            "status": status,
            "updated_at": datetime.now(),
        }
        if processed_count is not None:
            update_data["processed_count"] = int(processed_count)
        return await super().update(task_id, update_data)

    async def get_user_tasks(self, user_id: int, status: str = None) -> list:
        """Get all batch tasks for a specific user"""
        query = {"user_id": int(user_id)}
        if status:
            query["status"] = status
        return await super().filter_documents(query, sort=[("created_at", -1)])

    async def get_active_task(self, user_id: int) -> dict:
        """Get the currently active (running) task for a user"""
        query = {"user_id": int(user_id), "status": "running"}
        return await super().filter_document(query)

    async def get_distinct_chats(self) -> list[dict]:
        """
        Get all distinct source chats (source_chat_id and source_chat_title) from batch tasks.
        
        Returns:
            List of dicts containing 'chat_id' and 'channel_name'
        """
        pipeline = [
            {
                "$group": {
                    "_id": "$source_chat_id",
                    "channel_name": {"$first": "$source_chat_title"}
                }
            },
            {
                "$project": {
                    "chat_id": "$_id",
                    "channel_name": 1,
                    "_id": 0
                }
            }
        ]
        cursor = self.col.aggregate(pipeline)
        return await cursor.to_list(length=None)

    async def get_max_message_id(self, chat_id: int) -> Optional[int]:
        """Get the maximum last_message_id stored for a chat from batch tasks"""
        cursor = self.col.find({"source_chat_id": int(chat_id)}).sort("last_message_id", -1).limit(1)
        documents = await cursor.to_list(length=1)
        return documents[0]["last_message_id"] if documents else None
