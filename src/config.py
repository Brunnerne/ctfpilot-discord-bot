import argparse
import os
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_CATEGORIES = "web,crypto,pwn,misc"
DEFAULT_DIFFICULTIES = "easy,medium,hard"
DEFAULT_STATUSES = "Idea,Todo,In Progress,In review,Done"
DEFAULT_FLAG_PREFIX = "ctf"
DEFAULT_FLAG_LENGTH = 1000


@dataclass(frozen=True)
class BotConfig:
    discord_token: str
    discord_guild_id: str | None
    github_token: str
    github_repo: str
    github_project_id: str | None
    categories: list[str]
    difficulties: list[str]
    statuses: list[str]
    milestone_name: str
    allowed_role_ids: list[str]
    flag_prefix: str
    flag_length: int
    verbose: bool
    debug: bool

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_token and self.github_repo)


def load_config() -> BotConfig:
    """Load and validate bot configuration from CLI args and env."""
    load_dotenv()
    args = _parse_args()

    return BotConfig(
        discord_token=_resolve_value(args.token, "DISCORD_TOKEN"),
        discord_guild_id=_resolve_optional_value(args.guild, "DISCORD_GUILD_ID"),
        github_token=_resolve_value(args.gh_token, "GITHUB_TOKEN"),
        github_repo=_resolve_value(args.gh_repo, "GITHUB_REPO"),
        github_project_id=_resolve_optional_value(args.project_id, "GITHUB_PROJECT_ID"),
        categories=_resolve_list(args.categories, "CATEGORIES", DEFAULT_CATEGORIES),
        difficulties=_resolve_list(args.difficulties, "DIFFICULTIES", DEFAULT_DIFFICULTIES),
        statuses=_resolve_list(args.status, "STATUS", DEFAULT_STATUSES),
        milestone_name=_resolve_value(args.milestone, "MILESTONE", default=""),
        allowed_role_ids=_resolve_list(args.allowed_roles, "DISCORD_ALLOWED_ROLES", filter_empty=True),
        flag_prefix=_resolve_value(args.flag_prefix, "FLAG_PREFIX", default=DEFAULT_FLAG_PREFIX),
        flag_length=int(_resolve_value(args.flag_length, "FLAG_LENGTH", default=str(DEFAULT_FLAG_LENGTH))),
        verbose=_resolve_value(args.verbose, "VERBOSE", default="False").lower() == "true",
        debug=_resolve_value(args.debug, "DEBUG", default="False").lower() == "true"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discord Bot Manager")
    parser.add_argument("--token", type=str, help="Discord Bot Token")
    parser.add_argument("--guild", type=str, help="Discord Guild ID for command sync")
    parser.add_argument("--gh-token", type=str, help="GitHub Token for API access")
    parser.add_argument("--gh-repo", type=str, help="GitHub Repository for API access")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--categories", type=str, help="Comma-separated list of challenge categories")
    parser.add_argument("--difficulties", type=str, help="Comma-separated list of challenge difficulties")
    parser.add_argument("--project-id", type=str, help="GitHub Project ID (Projects v2)")
    parser.add_argument("--status", type=str, help="Comma-separated list of challenge status options")
    parser.add_argument("--milestone", type=str, help="Milestone name for created issues")
    parser.add_argument("--allowed-roles", type=str, help="Comma-separated list of Discord roles allowed to use restricted commands")
    parser.add_argument("--flag-prefix", type=str, help="Prefix for challenge flags before the flag brackets (e.g., ctf for ctf{...})")
    parser.add_argument("--flag-length", type=int, help="Length of the generated challenge flags")
    args, _ = parser.parse_known_args()
    return args


def _resolve_value(cli_value: str | None, env_name: str, default: str | None = None) -> str:
    env_value = os.getenv(env_name)
    value = cli_value or env_value or default

    return value or ""


def _resolve_optional_value(cli_value: str | None, env_name: str, default: str | None = None) -> str | None:
    value = _resolve_value(cli_value, env_name, default=default)
    return value or None


def _resolve_list(cli_value: str | None, env_name: str, default: str = "", filter_empty: bool = False) -> list[str]:
    raw_value = _resolve_value(cli_value, env_name, default=default)
    items = [item.strip() for item in raw_value.split(",")]
    if filter_empty:
        return [item for item in items if item]
    return items
