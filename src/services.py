from dataclasses import dataclass

from config import BotConfig
from exceptions.GithubInitializationException import GithubInitializationException
from github import Repository
from github_handler import GithubHandler
from logger import Logger

@dataclass(frozen=True)
class AppServices:
    gh: GithubHandler
    gh_repo: Repository.Repository
    github_repo_name: str
    github_enabled: bool
    project_id: str | None
    project_org: str | None
    project_number: str | None
    milestone_name: str

def initialize_services(config: BotConfig, logger: Logger) -> AppServices:
    github_repo_name = config.github_repo
    github_enabled = config.github_enabled
    project_org = github_repo_name.split("/")[0] if github_repo_name else None
    project_number = config.github_project_id
    project_id = None

    if not github_enabled:
        raise GithubInitializationException("GitHub not enabled due to missing configuration.")

    gh = GithubHandler(config.github_token, github_repo_name or "", logger)
    gh_repo = gh.repo

    gh.create_repo_labels(gh_repo, config.categories, config.difficulties)

    if project_org and project_number:
        try:
            project_number_int = int(project_number)
        except ValueError:
            logger.warning(f"Invalid GITHUB_PROJECT_ID '{project_number}', project commands will be disabled.")
            project_number_int = None

        if project_number_int is not None:
            project_id = gh.get_project_node_id(project_org, project_number_int, is_org=True)
            if not project_id:
                logger.error(f"Could not resolve project node ID for org={project_org}, number={project_number}")

    return AppServices(
        gh=gh,
        gh_repo=gh_repo,
        github_repo_name=github_repo_name,
        github_enabled=github_enabled,
        project_id=project_id,
        project_org=project_org,
        project_number=project_number,
        milestone_name=config.milestone_name)
