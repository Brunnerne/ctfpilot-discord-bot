import discord

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
