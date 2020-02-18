import os
from bot import EmailBotService
from dotenv import load_dotenv
load_dotenv()


if __name__ == "__main__":
    email_bot = EmailBotService(access_token=os.getenv("BOT_ACCESS_TOKEN"))
    email_bot.run_bot()
