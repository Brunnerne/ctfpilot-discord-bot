"""Dynamic cog loader for Discord.py commands."""

import importlib
import sys
import traceback
from pathlib import Path

from bot import BotClient
from utils import CommandContext


async def load_cogs(bot: BotClient, command_context: CommandContext) -> None:
    """
    Dynamically discover and load all cogs from the cogs directory.
    
    Each cog module must have a `setup(bot)` function that registers the cog.
    
    Args:
        bot: The Discord bot instance
        command_context: The command context containing logger, config, GitHub handler, etc.
    """
    bot.command_context = command_context
    
    cogs_path = Path(__file__).parent
    bot.command_context.logger.debug(f"Loading cogs from {cogs_path}")

    cog_files = [f for f in cogs_path.glob("*.py") if f.name not in ("__init__.py", "loader.py")]
    cog_packages = [d for d in cogs_path.iterdir() if d.is_dir() and (d / "__init__.py").exists() and d.name != "__pycache__"]

    for cog_path in sorted(cog_files + cog_packages):
        cog_name = cog_path.stem
        module_name = f"cogs.{cog_name}"
        
        try:
            # Dynamically import the cog module.
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)
            
            # Call the setup function to register the cog.
            if hasattr(module, "setup"):
                await module.setup(bot)
                bot.command_context.logger.info(f"Loaded cog: {cog_name}")
            else:
                bot.command_context.logger.warning(f"Cog {cog_name} does not have a setup() function, skipping")
        except Exception:
            bot.command_context.logger.error(f"Failed to load cog {cog_name}:\n{traceback.format_exc()}")
