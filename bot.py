import discord
from discord.ext import commands
from messages import (CREATE_TABLES)
import asyncpg
import os

class FicTracker(commands.Bot):
    def __init__(self, **options):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix='/',
            intents=intents,
            application_id=CLIENT_ID,
            **options
        )

    async def create_db_pool(self):
        bot.db = await asyncpg.create_pool(DATABASE)


    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await bot.load_extension(f'cogs.{filename[:-3]}')
        
        await self.create_db_pool()
        try:
            synced = await bot.tree.sync()
            print(f'Synced {len(synced)} commands')
        except Exception as e:
            print(e)

    async def close(self):
        await super().close()

    async def on_ready(self):
        print('Bot ready')
        await bot.db.execute(CREATE_TABLES)
    

TOKEN = os.getenv('TOKEN')
DATABASE = os.getenv('DATABASE')
CLIENT_ID = os.getenv('CLIENT_ID')

bot = FicTracker()
bot.run(TOKEN)