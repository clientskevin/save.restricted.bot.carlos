from .users import UserDatabase
from bot.config import Config
from .config import ConfigDB
from .user_channels import UserChannelDatabase
from .transfers import TransfersDB

class Database:
    def __init__(self):
        self.users = UserDatabase(Config.DATABASE_URL, Config.DATABASE_NAME)
        self.config = ConfigDB(Config.DATABASE_URL, Config.DATABASE_NAME)
        self.user_channels = UserChannelDatabase(Config.DATABASE_URL, Config.DATABASE_NAME)
        self.transfers = TransfersDB(Config.DATABASE_URL, Config.DATABASE_NAME)

db = Database()
