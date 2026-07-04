import discord
from dataclasses import dataclass
from discord import app_commands

from github import Repository

from github_handler import GithubHandler
from logger import Logger
from store import Store

# Precomputed translation tables for escaping
MARKDOWN_ESCAPE_CHARS = r"`*_{}[]()#+-.!|>"
MARKDOWN_ESCAPE_TRANSLATION = {ord(c): "\\" + c for c in MARKDOWN_ESCAPE_CHARS}
DISCORD_ESCAPE_CHARS = r"[]#@&<>"
DISCORD_ESCAPE_TRANSLATION = {ord(c): "\\" + c for c in DISCORD_ESCAPE_CHARS}

def is_authorized(interaction: discord.Interaction, guild_id: str | None, allowed_roles: list[str]) -> bool:
    """Check if the user has at least one allowed role (by ID) and is in an allowed guild."""
    # Check if interaction.guild is None
    if interaction.guild is None:
        return False

    # Check allowed guild
    interaction_guild_id = str(interaction.guild.id)
    if guild_id is not None and interaction_guild_id != guild_id:
        return False

    # Check allowed roles (by role ID)
    if not allowed_roles:
        return False

    if not hasattr(interaction.user, "roles"):
        return False

    return any(str(role.id) in allowed_roles for role in getattr(interaction.user, "roles", []))

def clean_input(text: str, field: str = "", min_len: int = 0, max_len: int = 100) -> str:
    """Sanitize user input for GitHub/Discord. Returns sanitized string or raises ValueError."""
    if not isinstance(text, str):
        raise ValueError(f"{field or 'Input'} must be a string.")
    text = text.strip()
    if len(text) < min_len:
        raise ValueError(f"{field or 'Input'} is too short (min {min_len} chars).")
    if len(text) > max_len:
        raise ValueError(f"{field or 'Input'} is too long (max {max_len} chars).")

    # Remove newlines and excessive whitespace
    return " ".join(text.split())

def markdown_clean(text: str, field: str = "", min_len: int = 0, max_len: int = 100) -> str:
    """Clean and escape markdown special characters in a string."""
    clean_text = clean_input(text, field=field, min_len=min_len, max_len=max_len)
    return clean_text.translate(MARKDOWN_ESCAPE_TRANSLATION)

def discord_clean(text: str, field: str = "", min_len: int = 0, max_len: int = 100) -> str:
    """Clean and escape Discord special characters in a string."""
    clean_text = clean_input(text, field=field, min_len=min_len, max_len=max_len)
    return clean_text.translate(DISCORD_ESCAPE_TRANSLATION)


##################
# Command Context
##################

async def _respond(interaction: discord.Interaction, content: str) -> None:
    """Reply to an interaction, editing the deferred response if one exists or sending ephemerally."""
    if interaction.response.is_done():
        await interaction.edit_original_response(content=content)
    else:
        await interaction.response.send_message(content, ephemeral=True)


async def resolve_issue_or_reply(interaction: discord.Interaction, issue_number: int | None) -> int | None:
    """Resolve the issue number from the argument or the channel mapping, replying if none is found."""
    if issue_number is None:
        issue_number = Store.get_challenge_key(str(interaction.channel_id))
    if not issue_number:
        await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
        return None
    return issue_number


@dataclass(frozen=True)
class CommandContext:
    logger: Logger
    gh: GithubHandler
    gh_repo: Repository.Repository
    github_repo_name: str
    github_enabled: bool
    project_id: str | None
    milestone_name: str
    guild_id: str | None
    allowed_roles: list[str]
    categories: list[str]
    difficulties: list[str]
    statuses: list[str]
    flag_prefix: str
    flag_length: int

    def is_authorized(self, interaction: discord.Interaction) -> bool:
        return is_authorized(interaction, self.guild_id, self.allowed_roles)

    def unauthorized_message(self) -> str:
        roles = ", ".join(self.allowed_roles) if self.allowed_roles else "None set"
        return f"❌ You must have one of the following roles to use this command: {roles}."

    async def deny_if_unauthorized(self, interaction: discord.Interaction) -> bool:
        if self.is_authorized(interaction):
            return False
        await _respond(interaction, self.unauthorized_message())
        return True

    async def deny_if_github_disabled(self, interaction: discord.Interaction) -> bool:
        if self.github_enabled:
            return False
        await _respond(interaction, "GitHub API features are disabled.")
        return True


def apply_config_choices(cog) -> None:
    """Populate config-driven choices on a cog's commands."""
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
