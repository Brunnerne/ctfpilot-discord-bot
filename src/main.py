import os
import argparse
import requests

from dotenv import load_dotenv

import discord
from discord import app_commands

from github import Github
from github import Auth

from logger import Logger
from store import Store
from typing import Optional

from github_handler import GithubHandler
from exceptions.WorkflowTriggerException import WorkflowTriggerException

logger: Logger

###################
# Startup configuration
###################

# Parse env/args for project config at module level
load_dotenv()

parser = argparse.ArgumentParser(description='Discord Bot Manager')
parser.add_argument('--token', type=str, help='Discord Bot Token')
parser.add_argument('--guild', type=str, help='Discord Guild ID for command sync')
parser.add_argument('--gh-token', type=str, help='GitHub Token for API access')
parser.add_argument('--gh-repo', type=str, help='GitHub Repository for API access')
parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
parser.add_argument('--debug', action='store_true', help='Enable debug logging')
parser.add_argument('--categories', type=str, help='Comma-separated list of challenge categories')
parser.add_argument('--difficulties', type=str, help='Comma-separated list of challenge difficulties')
parser.add_argument('--project-id', type=str, help='GitHub Project ID (Projects v2)')
parser.add_argument('--status', type=str, help='Comma-separated list of challenge status options')
parser.add_argument('--milestone', type=str, help='Milestone name for created issues')
parser.add_argument('--allowed-roles', type=str, help='Comma-separated list of Discord roles allowed to use restricted commands')
parser.add_argument('--flag-prefix', type=str, help='Prefix for challenge flags before the flag brackets (e.g., ctf for ctf{...})')
args, _ = parser.parse_known_args()

logger = Logger(verbose=args.verbose, debug=args.debug)
Store.initialize_db(logger)
    
if args.token:
    os.environ['DISCORD_TOKEN'] = args.token
if args.guild:
    os.environ['DISCORD_GUILD_ID'] = args.guild
if args.gh_token:
    os.environ['GITHUB_TOKEN'] = args.gh_token
if args.gh_repo:
    os.environ['GITHUB_REPO'] = args.gh_repo
if args.categories:
    os.environ['CATEGORIES'] = args.categories
if args.difficulties:
    os.environ['DIFFICULTIES'] = args.difficulties
if args.project_id:
    os.environ['GITHUB_PROJECT_ID'] = args.project_id
if args.status:
    os.environ['STATUS'] = args.status
if args.milestone:
    os.environ['MILESTONE'] = args.milestone
if args.allowed_roles:
    os.environ['DISCORD_ALLOWED_ROLES'] = args.allowed_roles
if args.flag_prefix:
    os.environ['FLAG_PREFIX'] = args.flag_prefix

if not os.getenv('DISCORD_TOKEN'):
    logger.error("Please set the DISCORD_TOKEN environment variable.")
    exit(1)
    
if not os.getenv('DISCORD_GUILD_ID'):
    logger.info("No DISCORD_GUILD_ID provided, commands will be synced globally.")
    
if not os.getenv('GITHUB_TOKEN'):
    logger.warning("No GITHUB_TOKEN provided, GitHub API features will be disabled.")
if not os.getenv('GITHUB_REPO'):
    logger.warning("No GITHUB_REPO provided, GitHub API features will be disabled.")

GUILD_ID = os.getenv('DISCORD_GUILD_ID')
if not GUILD_ID:
    logger.warning("No DISCORD_GUILD_ID provided, no commands will be available.")

CATEGORIES = [c.strip() for c in (os.getenv('CATEGORIES') or 'web,crypto,pwn,misc').split(',')]
DIFFICULTIES = [d.strip() for d in (os.getenv('DIFFICULTIES') or 'easy,medium,hard').split(',')]
STATUS = [s.strip() for s in (os.getenv('STATUS') or 'Idea,Todo,In Progress,In review,Done').split(',')]
ALLOWED_ROLES = [r.strip() for r in (os.getenv('DISCORD_ALLOWED_ROLES') or '').split(',') if r.strip()]
if len(ALLOWED_ROLES) == 0:
    logger.info("No DISCORD_ALLOWED_ROLES provided, no commands will be available.")

FLAG_PREFIX = os.getenv('FLAG_PREFIX') or "ctf"
FLAG_LENGTH = 1000

# --- GH configuration ---
GH_REPO = os.getenv('GITHUB_REPO')
gh_enabled = bool(os.getenv('GITHUB_TOKEN') and GH_REPO)
PROJECT_ORG = GH_REPO.split('/')[0] if GH_REPO else None
PROJECT_NUMBER = os.getenv('GITHUB_PROJECT_ID')  # This is the project number, not node ID
PROJECT_ID = None
MILESTONE_NAME = os.getenv('MILESTONE') or ""

if not gh_enabled:
    logger.error("GitHub not enabled due to missing configuration.")
    logger.error("Bot will not start")
    exit(1)

github: Github
github_token = os.getenv('GITHUB_TOKEN') or ""
gh = GithubHandler(github_token, GH_REPO or "", logger)
gh_repo = None

auth = Auth.Token(github_token)
github = Github(auth=auth)
gh_repo = github.get_repo(GH_REPO or "")

gh.create_repo_labels(gh_repo, CATEGORIES, DIFFICULTIES)

if PROJECT_ORG and PROJECT_NUMBER:
    PROJECT_ID = gh.get_project_node_id(PROJECT_ORG, int(PROJECT_NUMBER), is_org=True)
    if not PROJECT_ID:
        logger.error(f"Could not resolve project node ID for org={PROJECT_ORG}, number={PROJECT_NUMBER}")
else:
    PROJECT_ID = None

###################
# Bot configuration
###################

intents = discord.Intents.default()

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Sync commands to a specific guild for faster updates (optional)
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Slash commands synced to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Slash commands synced globally (may take up to 1 hour to appear)")

client = MyClient(intents=intents)

###################
# Discord commands
###################

@client.event
async def on_ready():
    logger.info(f'We have logged in as {client.user}')

@client.tree.command(name="challenges", description="List challenges in the GitHub.")
@app_commands.describe(
    status="Show all, open (non-finished), or closed (finished) challenges.",
    page="Page number to display (default: 1)"
)
@app_commands.choices(
    status=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Open (non-finished)", value="open"),
        app_commands.Choice(name="Closed (finished)", value="closed"),
    ]
)
async def issues(interaction: discord.Interaction, status: app_commands.Choice[str], page: Optional[int] = 1):
    await interaction.response.defer(thinking=True)
    if not is_authorized(interaction):
        await interaction.edit_original_response(content=f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.")
        return
    if not gh_enabled:
        await interaction.edit_original_response(content="GitHub API features are disabled.")
        return
    
    if not gh_repo:
        await interaction.edit_original_response(content="GitHub repository not set or could not be resolved. Command disabled.")
        return
    
    logger.info(f"Fetching {status.name} challenges from GitHub repository {gh_repo.full_name}")
    if status.value == "open":
        issues = gh_repo.get_issues(state="open", labels=['Challenge'])
    elif status.value == "closed":
        issues = gh_repo.get_issues(state="closed", labels=['Challenge'])
    else:
        issues = gh_repo.get_issues(state="all", labels=['Challenge'])
        
    issues = (issue for issue in issues if "/issues/" in issue.html_url)
    issues = list(issues)
    
    if not issues:
        await interaction.edit_original_response(content="No challenges found for this filter.")
        return
    
    # Pagination logic
    items_per_page = 10
    total_pages = (len(issues) + items_per_page - 1) // items_per_page  # Ceiling division
    
    # Ensure page has a valid value
    if page is None:
        page = 1
    
    # Validate page number
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    # Calculate slice indices
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    # Get the issues for the current page
    page_issues = issues[start_idx:end_idx]
    rows = [f"• [{issue.title}]({issue.html_url})" for issue in page_issues]
    
    msg = f"Challenges ({status.name}) - Page {page}/{total_pages}:\n" + "\n".join(rows)
    msg += f"\n\n[View all issues]({gh_repo.html_url}/issues)"
    await interaction.edit_original_response(content=msg)

# ------------------------------
# Challenge management commands
# ------------------------------

class ChallengeCreateGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="create", description="Create challenge resources.")

    @app_commands.command(name="issue", description="Create a new challenge issue on GitHub.")
    @app_commands.describe(
        name="Name of the challenge",
        category="Category of the challenge",
        difficulty="Difficulty of the challenge",
        status="Initial status for the challenge in the project"
    )
    @app_commands.choices(
        category=[app_commands.Choice(name=cat, value=cat) for cat in CATEGORIES],
        difficulty=[app_commands.Choice(name=diff, value=diff) for diff in DIFFICULTIES],
        status=[app_commands.Choice(name=s, value=s) for s in STATUS]
    )
    async def issue(self, interaction: discord.Interaction, name: str, category: app_commands.Choice[str], difficulty: app_commands.Choice[str], status: app_commands.Choice[str]):
        await interaction.response.defer(thinking=True)
        if not is_authorized(interaction):
            await interaction.edit_original_response(content=f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.")
            return
        try:
            safe_name = markdown_clean(name, field="Challenge name", min_len=3, max_len=100)
        except ValueError as e:
            await interaction.edit_original_response(content=f"❌ {e}")
            return
        if not gh_enabled:
            await interaction.edit_original_response(content="GitHub API features are disabled.")
            return
        if not PROJECT_ID:
            await interaction.edit_original_response(content="Project ID not set or could not be resolved. Command disabled.")
            return
        milestone_obj = gh.get_milestone(MILESTONE_NAME)
        labels = [
            "Challenge",
            f"Category: {category.value}",
            f"Difficulty: {difficulty.value}"
        ]
        issue_body = f"""
Challenge: {safe_name}

The issue was automatically created by the Discord bot, triggered by {markdown_clean(interaction.user.display_name, field="Display name", min_len=1, max_len=100)}.  
No code was generated, please trigger that manually, through the actions or the Discord bot.

This issue is linked to the Discord channel: [#{safe_name}](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}).
        """
        try:
            logger.debug(f"Creating issue with title: {safe_name}, body: {issue_body}, labels: {labels}, milestone: {milestone_obj.title if milestone_obj else 'None'}")
            issue = gh.create_issue(safe_name, issue_body, labels, milestone=milestone_obj)
            logger.debug(f"Created issue: {issue.title} (#{issue.number})")
            def update_challenges(challenges):
                if not isinstance(challenges, dict):
                    challenges = {}
                challenges[str(interaction.channel_id)] = issue.number
                return challenges
            Store.update_key("challenges", update_challenges)
            logger.debug(f"Challenges mapping updated: {Store.get_key('challenges', {})}")
            # Add issue to project and set status
            logger.debug(f"Adding issue {issue.node_id} to project {PROJECT_ID} with status '{status.value}'.")
            ok, err = gh.add_issue_to_project_and_set_status(issue.node_id, PROJECT_ID, status_name=status.value)
            logger.debug(f"Add to project result: {ok}, error: {err}")
            if ok:
                await interaction.edit_original_response(content=f"✅ Challenge issue created and added to project as '{status.value}': [{issue.title}]({issue.html_url})")
            else:
                await interaction.edit_original_response(content=f"✅ Challenge issue created, but failed to add to project: {err} [{issue.title}]({issue.html_url})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create GitHub issue: {e}")
            await interaction.edit_original_response(content=f"❌ Failed to create GitHub issue. Check if the issue already exists, otherwise contact an admin.")

    @app_commands.command(name="code", description="Trigger the GitHub pipeline to create challenge code.")
    @app_commands.describe(
        issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
        name="Name of the challenge (optional if used in mapped channel)",
        author="Author of the challenge",
        category="Category of the challenge (optional if used in mapped channel)",
        difficulty="Difficulty of the challenge (optional if used in mapped channel)",
        challenge_type="Type of challenge (static, online, instanced)",
        instanced_type="Type of instanced (none, tcp, web)",
        flag="Flag (format: " + FLAG_PREFIX + "{...}, dynamic, or null)"
    )
    @app_commands.choices(
        category=[app_commands.Choice(name=cat, value=cat) for cat in CATEGORIES],
        difficulty=[app_commands.Choice(name=diff, value=diff) for diff in DIFFICULTIES],
        challenge_type=[app_commands.Choice(name=t, value=t) for t in ["static", "online", "instanced"]],
        instanced_type=[app_commands.Choice(name=t, value=t) for t in ["none", "tcp", "web"]]
    )
    async def code(self, interaction: discord.Interaction, author: str, challenge_type: app_commands.Choice[str], instanced_type: app_commands.Choice[str], flag: str, name: Optional[str], category: Optional[app_commands.Choice[str]], difficulty: Optional[app_commands.Choice[str]], issue_number: Optional[int] = None):
        logger.debug(f"Received code command to create challenge code for issue #{issue_number}")
        await interaction.response.defer(thinking=True)
        if not is_authorized(interaction):
            await interaction.edit_original_response(content=f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.")
            return
        try:
            safe_author = clean_input(author, field="Author", min_len=3, max_len=50)
            safe_flag = clean_input(flag, field="Flag", min_len=3, max_len=FLAG_LENGTH) if flag else ""
        except ValueError as e:
            await interaction.edit_original_response(content=f"❌ Input error: {e}")
            return
        if not gh_enabled:
            await interaction.edit_original_response(content="GitHub API features are disabled.")
            return
        if issue_number is None:
            mapping = Store.get_key("challenges", {}) or {}
            issue_number = mapping.get(str(interaction.channel_id))
        if not issue_number:
            await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
            return
        
        safe_name = ""
        safe_category = ""
        safe_difficulty = ""
        
        try:
            gh_issue = gh.get_issue(issue_number)
            if gh_issue is not None and name is None:
                safe_name = clean_input(gh_issue.title, field="Challenge name", min_len=3, max_len=100)
            elif name:
                safe_name = clean_input(name, field="Challenge name", min_len=3, max_len=100)
            if gh_issue is not None and category is None:
                safe_category = gh.get_category(gh_issue) or ""
            elif category:
                safe_category = category.value
            if gh_issue is not None and difficulty is None:
                safe_difficulty = gh.get_difficulty(gh_issue) or ""
            elif difficulty:
                safe_difficulty = difficulty.value

            if safe_name == "":
                await interaction.edit_original_response(content="❌ Challenge name is required. Please provide a valid name.")
                return
            if safe_category == "":
                await interaction.edit_original_response(content="❌ Challenge category is required. Please provide a valid category.")
                return
            if safe_difficulty == "":
                await interaction.edit_original_response(content="❌ Challenge difficulty is required. Please provide a valid difficulty.")
                return
        except ValueError as e:
            await interaction.edit_original_response(content=f"❌ Input error: {e}")
            return

        try:
            gh.trigger_workflow(
                workflow_path="create-chall.yml",
                ref=gh.repo.default_branch,
                inputs={
                    "issue": str(issue_number),
                    "name": safe_name,
                    "author": safe_author,
                    "category": safe_category,
                    "difficulty": safe_difficulty,
                    "type": challenge_type.value,
                    "instanced_type": instanced_type.value,
                    "flag": safe_flag or ""
                }
            )
            logger.debug(f"Triggered workflow for issue #{issue_number} with inputs: name={safe_name}, author={safe_author}, category={safe_category}, difficulty={safe_difficulty}, type={challenge_type.value}, instanced_type={instanced_type.value}, flag={safe_flag}")
            actions_url = f"https://github.com/{GH_REPO}/actions/workflows/create-chall.yml"
            await interaction.edit_original_response(content=f"✅ Triggered pipeline for challenge code creation for issue [#{issue_number}]({gh.repo.html_url}/issues/{issue_number})\n\n Check the progress here: [Actions]({actions_url})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to trigger pipeline: {e}")
            await interaction.edit_original_response(content=f"❌ Failed to trigger pipeline. Please check if the pipeline is running, otherwise contact an admin.")
        except WorkflowTriggerException as e:
            logger.error(f"Failed to trigger pipeline: {e}")
            await interaction.edit_original_response(content=f"❌ Failed to trigger pipeline. Please check if the pipeline is running, otherwise contact an admin.")

class ChallengeUpdateGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="update", description="Update challenge properties.")

    @app_commands.command(name="difficulty", description="Update a challenge's difficulty.")
    @app_commands.describe(
        issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
        difficulty="New difficulty"
    )
    @app_commands.choices(
        difficulty=[app_commands.Choice(name=diff, value=diff) for diff in DIFFICULTIES]
    )
    async def difficulty(self, interaction: discord.Interaction, issue_number: Optional[int] = None, difficulty: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer(thinking=True)
        if not is_authorized(interaction):
            await interaction.edit_original_response(content=f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.")
            return
        if not gh_enabled:
            await interaction.edit_original_response(content="GitHub API features are disabled.")
            return
        if issue_number is None:
            mapping = Store.get_key("challenges", {})
            issue_number = mapping.get(str(interaction.channel_id)) if mapping else None
        if not issue_number:
            await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
            return
        try:
            issue = gh.get_issue(issue_number)
        except Exception as e:
            logger.error(f"Failed to retrieve issue #{issue_number}: {e}")
            await interaction.edit_original_response(content=f"❌ Could not retrieve issue #{issue_number}")
            return
        if difficulty:
            new_labels = [l.name for l in issue.labels if not l.name.startswith("Difficulty: ")]
            new_labels.append(f"Difficulty: {difficulty.value}")
            try:
                gh.set_issue_labels(issue, new_labels)
            except Exception as e:
                logger.error(f"Failed to set labels for issue #{issue.number}: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to update difficulty for challenge [#{issue.number}]({issue.html_url}).")
                return
            await interaction.edit_original_response(content=f"✅ Updated difficulty to {difficulty.value} for challenge [#{issue.number}]({issue.html_url})")
        else:
            await interaction.edit_original_response(content="No difficulty provided.")

    @app_commands.command(name="status", description="Update a challenge's status in the project.")
    @app_commands.describe(
        issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
        status="New status"
    )
    @app_commands.choices(
        status=[app_commands.Choice(name=s, value=s) for s in STATUS]
    )
    async def status(self, interaction: discord.Interaction, issue_number: Optional[int] = None, status: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer(thinking=True)
        if not is_authorized(interaction):
            await interaction.edit_original_response(content=f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.")
            return
        if not gh_enabled:
            await interaction.edit_original_response(content="GitHub API features are disabled.")
            return
        if not PROJECT_ID:
            await interaction.edit_original_response(content="Project ID not set or could not be resolved. Command disabled.")
            return
        if issue_number is None:
            mapping = Store.get_key("challenges", {})
            issue_number = mapping.get(str(interaction.channel_id)) if mapping else None
        if not issue_number:
            await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
            return
        try:
            issue = gh.get_issue(issue_number)
            ok, err = gh.add_issue_to_project_and_set_status(issue.node_id, PROJECT_ID, status_name=status.value if status else "Idea")
            if ok:
                await interaction.edit_original_response(content=f"✅ Updated status to {status.value if status else 'Idea'} for challenge [#{issue.number}]({issue.html_url})")
            else:
                logger.error(f"Failed to update status for issue #{issue.number}: {err}")
                await interaction.edit_original_response(content=f"❌ Failed to update status for challenge [#{issue.number}]({issue.html_url}).")
        except Exception as e:
            logger.error(f"Error retrieving issue #{issue_number}: {e}")
            await interaction.edit_original_response(content=f"❌ Failed to retrieve issue #{issue_number}. It may not exist or there was an API error.")

    @app_commands.command(name="category", description="Update a challenge's category.")
    @app_commands.describe(
        issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
        category="New category"
    )
    @app_commands.choices(
        category=[app_commands.Choice(name=cat, value=cat) for cat in CATEGORIES]
    )
    async def category(self, interaction: discord.Interaction, issue_number: Optional[int] = None, category: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer(thinking=True)
        if not is_authorized(interaction):
            await interaction.edit_original_response(content=f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.")
            return
        if not gh_enabled:
            await interaction.edit_original_response(content="GitHub API features are disabled.")
            return
        if issue_number is None:
            mapping = Store.get_key("challenges", {})
            issue_number = mapping.get(str(interaction.channel_id)) if mapping else None
        if not issue_number:
            await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
            return
        try:
            issue = gh.get_issue(issue_number)
        except Exception as e:
            logger.error(f"Failed to retrieve issue #{issue_number}: {e}")
            await interaction.edit_original_response(content=f"❌ Could not retrieve issue #{issue_number}")
            return
        if category:
            new_labels = [l.name for l in issue.labels if not l.name.startswith("Category: ")]
            new_labels.append(f"Category: {category.value}")
            try:
                gh.set_issue_labels(issue, new_labels)
            except Exception as e:
                logger.error(f"Failed to set labels for issue #{issue.number}: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to update category for challenge [#{issue.number}]({issue.html_url}).")
                return
            await interaction.edit_original_response(content=f"✅ Updated category to {category.value} for challenge [#{issue.number}]({issue.html_url})")
        else:
            await interaction.edit_original_response(content="No category provided.")

    @app_commands.command(name="name", description="Update a challenge's name (issue title).")
    @app_commands.describe(
        issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
        name="New name for the challenge"
    )
    async def update_name(self, interaction: discord.Interaction, issue_number: Optional[int] = None, name: Optional[str] = None):
        await interaction.response.defer(thinking=True)
        if not is_authorized(interaction):
            await interaction.edit_original_response(content=f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.")
            return
        if not gh_enabled:
            await interaction.edit_original_response(content="GitHub API features are disabled.")
            return
        if issue_number is None:
            mapping = Store.get_key("challenges", {})
            issue_number = mapping.get(str(interaction.channel_id)) if mapping else None
        if not issue_number:
            await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
            return
        if not name:
            await interaction.edit_original_response(content="No name provided.")
            return
        try:
            safe_name = markdown_clean(name, field="Challenge name", min_len=3, max_len=100)
        except ValueError as e:
            await interaction.edit_original_response(content=f"❌ {e}")
            return
        try:  
            issue = gh.get_issue(issue_number)  
            issue.edit(title=safe_name)  
        except Exception as e:  
            await interaction.edit_original_response(content=f"❌ Failed to update challenge name: {e}")  
            return 
        await interaction.edit_original_response(content=f"✅ Updated challenge name to '{safe_name}' for [#{issue.number}]({issue.html_url})")

challenge_group = app_commands.Group(name="challenge", description="Challenge management commands.")
challenge_group.add_command(ChallengeCreateGroup())
challenge_group.add_command(ChallengeUpdateGroup())
client.tree.add_command(challenge_group)

@challenge_group.command(name="clear_channel", description="Clear the issue-channel mapping for this channel.")
async def clear_channel(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message(f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.", ephemeral=True)
        return
    mapping = Store.get_key("challenges", {}) or {}
    channel_id = str(interaction.channel_id)
    if channel_id in mapping:
        Store.delete_challenge_key(channel_id)
        await interaction.response.send_message("✅ Cleared issue-channel mapping for this channel.", ephemeral=True)
    else:
        await interaction.response.send_message("No issue linked to this channel.", ephemeral=True)

@challenge_group.command(name="link_channel", description="Manually link an issue to this channel.")
@app_commands.describe(issue_number="GitHub issue number to link to this channel.")
async def link_channel(interaction: discord.Interaction, issue_number: int):
    if not is_authorized(interaction):
        await interaction.response.send_message(f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.", ephemeral=True)
        return
    Store.set_challenge_key(str(interaction.channel_id), issue_number)
    await interaction.response.send_message(f"✅ Linked issue #{issue_number} to this channel.", ephemeral=True)

@challenge_group.command(name="info", description="Show information about the current challenge (from channel or by issue number)")
@app_commands.describe(issue_number="GitHub issue number for the challenge (optional if used in mapped channel)")
async def info(interaction: discord.Interaction, issue_number: Optional[int] = None):
    if not is_authorized(interaction):
        await interaction.response.send_message(f"❌ You must have one of the following roles to use this command: {', '.join(ALLOWED_ROLES) if ALLOWED_ROLES else 'None set'}.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    if issue_number is None:
        mapping = Store.get_key("challenges", {}) or {}
        issue_number = mapping.get(str(interaction.channel_id)) if mapping else None
    if not issue_number:
        await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
        return
    try:
        issue = gh.get_issue(issue_number)
        # Extract fields
        name = issue.title
        assignees = ', '.join([a.login for a in issue.assignees]) if issue.assignees else 'None'
        labels = [l.name for l in issue.labels]
        difficulty = next((l.split(':',1)[1].strip() for l in labels if l.lower().startswith('difficulty:')), 'Unknown')
        category = next((l.split(':',1)[1].strip() for l in labels if l.lower().startswith('category:')), 'Unknown')
        global_status = 'Open' if issue.state == 'open' else 'Closed'
        # Try to get project status
        project_status = 'Unknown'
        if PROJECT_ID:
            try:
                project_status = gh.get_issue_project_status(issue.number, PROJECT_ID, issue.node_id)
            except Exception as e:
                logger.error(f"Error fetching project status: {e}")
        info_msg = (
            f"**Challenge Info**\n"
            f"Title: {discord_clean(name, max_len=256)}\n"
            f"Assignees: {discord_clean(assignees, max_len=256)}\n"
            f"Difficulty: {discord_clean(difficulty, max_len=256)}\n"
            f"Category: {discord_clean(category, max_len=256)}\n"
            f"Project Status: {discord_clean(project_status, max_len=256)}\n"
            f"Issue Status: {discord_clean(global_status, max_len=256)}"
            f"\n\n"
            f"[View Issue]({issue.html_url})\n"
            f"[View Repository]({gh.repo.html_url})\n"
        )
        await interaction.edit_original_response(content=info_msg)
    except Exception as e:
        logger.error(f"Failed to fetch issue info: {e}")
        await interaction.edit_original_response(content="❌ Failed to fetch challenge info. Please contact an admin.")

def is_authorized(interaction: discord.Interaction) -> bool:
    """Check if the user has at least one allowed role (by ID) and is in an allowed guild."""
    # Check if interaction.guild is None
    if interaction.guild is None:
        return False
    # Check allowed guild
    guild_id = str(interaction.guild.id)
    if GUILD_ID is not None and guild_id != GUILD_ID:
        return False
    # Check allowed roles (by role ID)
    if not ALLOWED_ROLES:
        return False
    if not hasattr(interaction.user, 'roles'):
        return False
    return any(str(role.id) in ALLOWED_ROLES for role in getattr(interaction.user, 'roles', []))

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
    text = ' '.join(text.split())
    
    return text

# Precomputed translation tables for escaping
MARKDOWN_ESCAPE_CHARS = r"`*_{}[]()#+-.!|>"
MARKDOWN_ESCAPE_TRANSLATION = {ord(c): "\\" + c for c in MARKDOWN_ESCAPE_CHARS}
DISCORD_ESCAPE_CHARS = r"[]#@&<>"
DISCORD_ESCAPE_TRANSLATION = {ord(c): "\\" + c for c in DISCORD_ESCAPE_CHARS}

def markdown_clean(text: str, field: str = "", min_len: int = 0, max_len: int = 100) -> str:
    """Clean and escape markdown special characters in a string."""
    clean_text = clean_input(text, field=field, min_len=min_len, max_len=max_len)
    return clean_text.translate(MARKDOWN_ESCAPE_TRANSLATION)

def discord_clean(text: str, field: str = "", min_len: int = 0, max_len: int = 100) -> str:
    """Clean and escape Discord special characters in a string."""
    clean_text = clean_input(text, field=field, min_len=min_len, max_len=max_len)
    return clean_text.translate(DISCORD_ESCAPE_TRANSLATION)

client.run(os.getenv('DISCORD_TOKEN') or "")
