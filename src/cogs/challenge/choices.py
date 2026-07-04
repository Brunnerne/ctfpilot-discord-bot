"""Populate config-driven command choices from the runtime context."""

from discord import app_commands


def apply_config_choices(cog):
    ctx = cog.bot.command_context
    fields = {
        "category": ctx.categories,
        "difficulty": ctx.difficulties,
        "status": ctx.statuses,
    }
    for cmd in cog.walk_app_commands():
        if not isinstance(cmd, app_commands.Command):
            continue
        for name, values in fields.items():
            if name in cmd._params:
                cmd._params[name].choices = [app_commands.Choice(name=v, value=v) for v in values]
