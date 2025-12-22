from database.core import Core


class UserChannelDatabase(Core):
    def __init__(self, uri, database_name):
        key = "user_channels"
        super().__init__(uri, database_name, key)

    async def create(self, title, user_id, channel_id, topic_id):
        return await super().create(
            {
                "title": title,
                "user_id": user_id,
                "channel_id": channel_id,
                "topic_id": topic_id,
                "paid_media": {"stars": 0, "status": False},
                "status": True,
            }
        )
