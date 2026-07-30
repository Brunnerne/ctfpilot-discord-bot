"""Challenge management cog for the /challenge command group."""

from utils import apply_config_choices

from .cog import ChallengeCog


async def setup(bot):
    cog = ChallengeCog(bot)
    await bot.add_cog(cog)
    apply_config_choices(cog)
