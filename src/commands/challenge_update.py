from typing import Optional

import discord
from discord import app_commands

from store import Store
from utils import markdown_clean, CommandContext


def build_challenge_update_group(ctx: CommandContext) -> app_commands.Group:
    class ChallengeUpdateGroup(app_commands.Group):
        def __init__(self):
            super().__init__(name="update", description="Update challenge properties.")

        @app_commands.command(name="difficulty", description="Update a challenge's difficulty.")
        @app_commands.describe(
            issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
            difficulty="New difficulty"
        )
        @app_commands.choices(
            difficulty=[app_commands.Choice(name=diff, value=diff) for diff in ctx.difficulties]
        )
        async def difficulty(self, interaction: discord.Interaction, issue_number: Optional[int] = None, difficulty: Optional[app_commands.Choice[str]] = None):
            await interaction.response.defer(thinking=True)
            if not ctx.is_authorized(interaction):
                await interaction.edit_original_response(content=ctx.unauthorized_message())
                return
            if not ctx.github_enabled:
                await interaction.edit_original_response(content="GitHub API features are disabled.")
                return
            if issue_number is None:
                mapping = Store.get_key("challenges", {})
                issue_number = mapping.get(str(interaction.channel_id)) if mapping else None
            if not issue_number:
                await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
                return
            try:
                issue = ctx.gh.get_issue(issue_number)
            except Exception as e:
                ctx.logger.error(f"Failed to retrieve issue #{issue_number}: {e}")
                await interaction.edit_original_response(content=f"❌ Could not retrieve issue #{issue_number}")
                return
            if difficulty:
                new_labels = [l.name for l in issue.labels if not l.name.startswith("Difficulty: ")]
                new_labels.append(f"Difficulty: {difficulty.value}")
                try:
                    ctx.gh.set_issue_labels(issue, new_labels)
                except Exception as e:
                    ctx.logger.error(f"Failed to set labels for issue #{issue.number}: {e}")
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
            status=[app_commands.Choice(name=s, value=s) for s in ctx.statuses]
        )
        async def status(self, interaction: discord.Interaction, issue_number: Optional[int] = None, status: Optional[app_commands.Choice[str]] = None):
            await interaction.response.defer(thinking=True)
            if not ctx.is_authorized(interaction):
                await interaction.edit_original_response(content=ctx.unauthorized_message())
                return
            if not ctx.github_enabled:
                await interaction.edit_original_response(content="GitHub API features are disabled.")
                return
            if not ctx.project_id:
                await interaction.edit_original_response(content="Project ID not set or could not be resolved. Command disabled.")
                return
            if issue_number is None:
                mapping = Store.get_key("challenges", {})
                issue_number = mapping.get(str(interaction.channel_id)) if mapping else None
            if not issue_number:
                await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
                return
            try:
                issue = ctx.gh.get_issue(issue_number)
                ok, err = ctx.gh.add_issue_to_project_and_set_status(issue.node_id, ctx.project_id, status_name=status.value if status else "Idea")
                if ok:
                    await interaction.edit_original_response(content=f"✅ Updated status to {status.value if status else 'Idea'} for challenge [#{issue.number}]({issue.html_url})")
                else:
                    ctx.logger.error(f"Failed to update status for issue #{issue.number}: {err}")
                    await interaction.edit_original_response(content=f"❌ Failed to update status for challenge [#{issue.number}]({issue.html_url}).")
            except Exception as e:
                ctx.logger.error(f"Error retrieving issue #{issue_number}: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to retrieve issue #{issue_number}. It may not exist or there was an API error.")

        @app_commands.command(name="category", description="Update a challenge's category.")
        @app_commands.describe(
            issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
            category="New category"
        )
        @app_commands.choices(
            category=[app_commands.Choice(name=cat, value=cat) for cat in ctx.categories]
        )
        async def category(self, interaction: discord.Interaction, issue_number: Optional[int] = None, category: Optional[app_commands.Choice[str]] = None):
            await interaction.response.defer(thinking=True)
            if not ctx.is_authorized(interaction):
                await interaction.edit_original_response(content=ctx.unauthorized_message())
                return
            if not ctx.github_enabled:
                await interaction.edit_original_response(content="GitHub API features are disabled.")
                return
            if issue_number is None:
                mapping = Store.get_key("challenges", {})
                issue_number = mapping.get(str(interaction.channel_id)) if mapping else None
            if not issue_number:
                await interaction.edit_original_response(content="No issue found for this channel. Please specify an issue number.")
                return
            try:
                issue = ctx.gh.get_issue(issue_number)
            except Exception as e:
                ctx.logger.error(f"Failed to retrieve issue #{issue_number}: {e}")
                await interaction.edit_original_response(content=f"❌ Could not retrieve issue #{issue_number}")
                return
            if category:
                new_labels = [l.name for l in issue.labels if not l.name.startswith("Category: ")]
                new_labels.append(f"Category: {category.value}")
                try:
                    ctx.gh.set_issue_labels(issue, new_labels)
                except Exception as e:
                    ctx.logger.error(f"Failed to set labels for issue #{issue.number}: {e}")
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
            if not ctx.is_authorized(interaction):
                await interaction.edit_original_response(content=ctx.unauthorized_message())
                return
            if not ctx.github_enabled:
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
                issue = ctx.gh.get_issue(issue_number)  
                issue.edit(title=safe_name)  
            except Exception as e:  
                await interaction.edit_original_response(content=f"❌ Failed to update challenge name: {e}")  
                return 
            await interaction.edit_original_response(content=f"✅ Updated challenge name to '{safe_name}' for [#{issue.number}]({issue.html_url})")

    return ChallengeUpdateGroup()
