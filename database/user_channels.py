from database.core import Core


class UserChannelDatabase(Core):
    def __init__(self, uri, database_name):
        key = "user_channels"
        super().__init__(uri, database_name, key)

    async def create(
        self,
        user_id: int,
        source_channel_id: int,
        source_title: str,
        destination_channel_id: int,
        destination_title: str,
        topic_id: int | None,
    ):
        return await super().create(
            {
                "user_id": user_id,
                "source_channel_id": source_channel_id,
                "source_title": source_title,
                "destination_channel_id": destination_channel_id,
                "destination_title": destination_title,
                "topic_id": topic_id,
                "paid_media": {"stars": 0, "status": False},
                "status": True,
            }
        )
