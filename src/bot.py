from typing import Optional

import discord
from discord.ext import commands

from logger import Logger
from utils import CommandContext


class BotClient(commands.Bot):
    def __init__(self, guild_id: Optional[str], logger: Logger, command_context: CommandContext, *args, **kwargs):
        super().__init__(command_prefix="/", *args, **kwargs)
        self.guild_id = guild_id
        self.logger = logger
        self.command_context = command_context

    async def setup_hook(self):
        from cogs.loader import load_cogs
        await load_cogs(self, self.command_context)
        
        # Sync commands to a specific guild for faster updates (optional)
        if self.guild_id:
            guild = discord.Object(id=int(self.guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.logger.info(f"Slash commands synced to guild {self.guild_id}")
        else:
            await self.tree.sync()
            self.logger.info("Slash commands synced globally (may take up to 1 hour to appear)")

BotInteraction = discord.Interaction[BotClient]

def create_client(guild_id: Optional[str], logger: Logger, command_context: CommandContext) -> BotClient:
    return BotClient(
        guild_id=guild_id,
        logger=logger,
        command_context=command_context,
        intents=discord.Intents.default(),
        allowed_mentions=discord.AllowedMentions.none())
