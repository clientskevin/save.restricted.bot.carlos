import os
from bot import Bot
from bot.utils import resume_transfers
from apscheduler.schedulers.asyncio import AsyncIOScheduler


if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    sc = AsyncIOScheduler()
    sc.start()
    app = Bot()
    app.sc = sc

    sc.add_job(resume_transfers, args=[app])

    app.run()
