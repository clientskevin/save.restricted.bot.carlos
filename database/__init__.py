from bot.config import Config

from .config import ConfigDB
from .messages import MessagesDB
from .notion_mapping import NotionMappingDB
from .transfers import TransfersDB
from .user_channels import UserChannelDatabase
from .users import UserDatabase


class Database:
    def __init__(self):
        self.users = UserDatabase(Config.DATABASE_URL, Config.DATABASE_NAME)
        self.config = ConfigDB(Config.DATABASE_URL, Config.DATABASE_NAME)
        self.user_channels = UserChannelDatabase(Config.DATABASE_URL, Config.DATABASE_NAME)
        self.transfers = TransfersDB(Config.DATABASE_URL, Config.DATABASE_NAME)
        self.messages = MessagesDB(Config.DATABASE_URL, Config.DATABASE_NAME)
        self.notion_mapping = NotionMappingDB(Config.DATABASE_URL, Config.DATABASE_NAME)

db = Database()
