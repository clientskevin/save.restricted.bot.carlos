from database.core import Core


class NotionConfigDB(Core):
    def __init__(self, uri, database_name):
        super().__init__(uri, database_name, "notion_config")

    async def get_or_create(self):
        doc = await self.col.find_one({"_id": "singleton"})
        if not doc:
            doc = {"_id": "singleton", "NOTION_PARENT_PAGE_ID": None}
            await self.col.insert_one(doc)
        return doc

    async def update_page_id(self, page_id):
        await self.get_or_create()
        return await super().update("singleton", {"NOTION_PARENT_PAGE_ID": page_id})

    async def get_page_id(self):
        doc = await self.get_or_create()
        return doc.get("NOTION_PARENT_PAGE_ID")