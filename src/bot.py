from typing import Optional

import discord
from discord import app_commands

from logger import Logger


class MyClient(discord.Client):
    def __init__(self, guild_id: Optional[str], logger: Logger, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild_id = guild_id
        self.logger = logger
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Sync commands to a specific guild for faster updates (optional)
        if self.guild_id:
            guild = discord.Object(id=int(self.guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.logger.info(f"Slash commands synced to guild {self.guild_id}")
        else:
            await self.tree.sync()
            self.logger.info("Slash commands synced globally (may take up to 1 hour to appear)")


def create_client(guild_id: Optional[str], logger: Logger) -> MyClient:
    intents = discord.Intents.default()
    return MyClient(guild_id=guild_id, logger=logger, intents=intents)
