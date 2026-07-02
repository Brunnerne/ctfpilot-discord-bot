from discord import app_commands

from commands.challenge_create import build_challenge_create_group
from commands.challenge_misc import register_challenge_misc_commands
from commands.challenge_update import build_challenge_update_group
from commands.context import CommandContext


def register_challenge_commands(tree: app_commands.CommandTree, ctx: CommandContext) -> None:
    challenge_group = app_commands.Group(name="challenge", description="Challenge management commands.")
    challenge_group.add_command(build_challenge_create_group(ctx))
    challenge_group.add_command(build_challenge_update_group(ctx))
    register_challenge_misc_commands(challenge_group, ctx)
    tree.add_command(challenge_group)
