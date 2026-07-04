from bot import create_client
from utils import CommandContext
from config import load_config
from exceptions.GithubInitializationException import GithubInitializationException
from logger import Logger
from services import initialize_services
from store import Store

logger: Logger

###################
# Startup configuration
###################

config = load_config()
logger = Logger(verbose=config.verbose, debug=config.debug)
Store.initialize_db(logger)

if not config.discord_token:
    logger.error("Please set the DISCORD_TOKEN environment variable.")
    exit(1)

guild_id = config.discord_guild_id
if not guild_id:
    logger.info("No DISCORD_GUILD_ID provided, commands will be synced globally.")

if not config.github_token:
    logger.warning("No GITHUB_TOKEN provided, GitHub API features will be disabled.")
if not config.github_repo:
    logger.warning("No GITHUB_REPO provided, GitHub API features will be disabled.")

if len(config.allowed_role_ids) == 0:
    logger.info("No DISCORD_ALLOWED_ROLES provided, no commands will be available.")

# --- GH configuration ---
try:
    services = initialize_services(config, logger)
except GithubInitializationException as e:
    logger.error(str(e))
    logger.error("Bot will not start")
    exit(1)

command_context = CommandContext(
    logger=logger,
    gh=services.gh,
    gh_repo=services.gh_repo,
    github_repo_name=services.github_repo_name,
    github_enabled=services.github_enabled,
    project_id=services.project_id,
    milestone_name=services.milestone_name,
    guild_id=guild_id,
    allowed_roles=config.allowed_role_ids,
    categories=config.categories,
    difficulties=config.difficulties,
    statuses=config.statuses,
    flag_prefix=config.flag_prefix,
    flag_length=config.flag_length)

###################
# Bot configuration
###################

client = create_client(guild_id, logger, command_context)

###################
# Discord commands
###################

@client.event
async def on_ready():
    logger.info(f'Logged in as {client.user}')


client.run(config.discord_token)
