from dataclasses import dataclass

import discord
from github import Repository

from github_handler import GithubHandler
from logger import Logger
from utils import is_authorized as user_is_authorized


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
        return user_is_authorized(interaction, self.guild_id, self.allowed_roles)

    def unauthorized_message(self) -> str:
        roles = ", ".join(self.allowed_roles) if self.allowed_roles else "None set"
        return f"❌ You must have one of the following roles to use this command: {roles}."
