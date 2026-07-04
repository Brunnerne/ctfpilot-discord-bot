from typing import Optional

import requests

import discord
from discord import app_commands

from exceptions.WorkflowTriggerException import WorkflowTriggerException
from store import Store
from utils import clean_input, markdown_clean, CommandContext


def build_challenge_create_group(ctx: CommandContext) -> app_commands.Group:
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
            category=[app_commands.Choice(name=cat, value=cat) for cat in ctx.categories],
            difficulty=[app_commands.Choice(name=diff, value=diff) for diff in ctx.difficulties],
            status=[app_commands.Choice(name=s, value=s) for s in ctx.statuses]
        )
        async def issue(self, interaction: discord.Interaction, name: str, category: app_commands.Choice[str], difficulty: app_commands.Choice[str], status: app_commands.Choice[str]):
            await interaction.response.defer(thinking=True)
            if not ctx.is_authorized(interaction):
                await interaction.edit_original_response(content=ctx.unauthorized_message())
                return
            try:
                safe_name = markdown_clean(name, field="Challenge name", min_len=3, max_len=100)
            except ValueError as e:
                await interaction.edit_original_response(content=f"❌ {e}")
                return
            if not ctx.github_enabled:
                await interaction.edit_original_response(content="GitHub API features are disabled.")
                return
            if not ctx.project_id:
                await interaction.edit_original_response(content="Project ID not set or could not be resolved. Command disabled.")
                return
            milestone_obj = ctx.gh.get_milestone(ctx.milestone_name)
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
                ctx.logger.debug(f"Creating issue with title: {safe_name}, body: {issue_body}, labels: {labels}, milestone: {milestone_obj.title if milestone_obj else 'None'}")
                issue = ctx.gh.create_issue(safe_name, issue_body, labels, milestone=milestone_obj)
                ctx.logger.debug(f"Created issue: {issue.title} (#{issue.number})")
                def update_challenges(challenges):
                    if not isinstance(challenges, dict):
                        challenges = {}
                    challenges[str(interaction.channel_id)] = issue.number
                    return challenges
                Store.update_key("challenges", update_challenges)
                ctx.logger.debug(f"Challenges mapping updated: {Store.get_key('challenges', {})}")
                # Add issue to project and set status
                ctx.logger.debug(f"Adding issue {issue.node_id} to project {ctx.project_id} with status '{status.value}'.")
                ok, err = ctx.gh.add_issue_to_project_and_set_status(issue.node_id, ctx.project_id, status_name=status.value)
                ctx.logger.debug(f"Add to project result: {ok}, error: {err}")
                if ok:
                    await interaction.edit_original_response(content=f"✅ Challenge issue created and added to project as '{status.value}': [{issue.title}]({issue.html_url})")
                else:
                    await interaction.edit_original_response(content=f"✅ Challenge issue created, but failed to add to project: {err} [{issue.title}]({issue.html_url})")
            except requests.exceptions.RequestException as e:
                ctx.logger.error(f"Failed to create GitHub issue: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to create GitHub issue. Check if the issue already exists, otherwise contact an admin.")

        @app_commands.command(name="code", description="Trigger the GitHub pipeline to create challenge code.")
        @app_commands.describe(
            issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
            name="Name of the challenge (optional if used in mapped channel)",
            author="Author of the challenge",
            category="Category of the challenge (optional if used in mapped channel)",
            difficulty="Difficulty of the challenge (optional if used in mapped channel)",
            challenge_type="Type of challenge (static, shared, instanced)",
            instanced_type="Type of instanced (none, tcp, web)",
            flag="Flag (format: " + ctx.flag_prefix + "{...}, dynamic, or null)"
        )
        @app_commands.choices(
            category=[app_commands.Choice(name=cat, value=cat) for cat in ctx.categories],
            difficulty=[app_commands.Choice(name=diff, value=diff) for diff in ctx.difficulties],
            challenge_type=[app_commands.Choice(name=t, value=t) for t in ["static", "shared", "instanced"]],
            instanced_type=[app_commands.Choice(name=t, value=t) for t in ["none", "tcp", "web"]]
        )
        async def code(self, interaction: discord.Interaction, author: str, challenge_type: app_commands.Choice[str], instanced_type: app_commands.Choice[str], flag: str, name: Optional[str], category: Optional[app_commands.Choice[str]], difficulty: Optional[app_commands.Choice[str]], issue_number: Optional[int] = None):
            ctx.logger.debug(f"Received code command to create challenge code for issue #{issue_number}")
            await interaction.response.defer(thinking=True)
            if not ctx.is_authorized(interaction):
                await interaction.edit_original_response(content=ctx.unauthorized_message())
                return
            try:
                safe_author = clean_input(author, field="Author", min_len=3, max_len=50)
                safe_flag = clean_input(flag, field="Flag", min_len=3, max_len=ctx.flag_length)
            except ValueError as e:
                await interaction.edit_original_response(content=f"❌ Input error: {e}")
                return
            if not ctx.github_enabled:
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
                gh_issue = ctx.gh.get_issue(issue_number)
                if gh_issue is not None and name is None:
                    safe_name = clean_input(gh_issue.title, field="Challenge name", min_len=3, max_len=100)
                elif name:
                    safe_name = clean_input(name, field="Challenge name", min_len=3, max_len=100)
                if gh_issue is not None and category is None:
                    safe_category = ctx.gh.get_category(gh_issue) or ""
                elif category:
                    safe_category = category.value
                if gh_issue is not None and difficulty is None:
                    safe_difficulty = ctx.gh.get_difficulty(gh_issue) or ""
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
                ctx.gh.trigger_workflow(
                    workflow_path="create-chall.yml",
                    ref=ctx.gh.repo.default_branch,
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
                ctx.logger.debug(f"Triggered workflow for issue #{issue_number} with inputs: name={safe_name}, author={safe_author}, category={safe_category}, difficulty={safe_difficulty}, type={challenge_type.value}, instanced_type={instanced_type.value}, flag={safe_flag}")
                actions_url = f"https://github.com/{ctx.github_repo_name}/actions/workflows/create-chall.yml"
                await interaction.edit_original_response(content=f"✅ Triggered pipeline for challenge code creation for issue [#{issue_number}]({ctx.gh.repo.html_url}/issues/{issue_number})\n\n Check the progress here: [Actions]({actions_url})")
            except requests.exceptions.RequestException as e:
                ctx.logger.error(f"Failed to trigger pipeline: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to trigger pipeline. Please check if the pipeline is running, otherwise contact an admin.")
            except WorkflowTriggerException as e:
                ctx.logger.error(f"Failed to trigger pipeline: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to trigger pipeline. Please check if the pipeline is running, otherwise contact an admin.")

    return ChallengeCreateGroup()
