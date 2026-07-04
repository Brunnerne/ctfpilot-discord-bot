"""Subgroup for /challenge update commands."""

from typing import Optional

from discord import app_commands

from bot import BotInteraction
from utils import markdown_clean, resolve_issue_or_reply


class UpdateGroup(app_commands.Group, name="update", description="Update challenge properties."):

    @app_commands.command(name="difficulty", description="Update a challenge's difficulty.")
    @app_commands.describe(
        issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
        difficulty="New difficulty"
    )
    async def update_difficulty(self, interaction: BotInteraction, difficulty: str, issue_number: Optional[int] = None):
        await interaction.response.defer(thinking=True)
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return
        if await ctx.deny_if_github_disabled(interaction):
            return
        issue_number = await resolve_issue_or_reply(interaction, issue_number)
        if issue_number is None:
            return
        try:
            issue = ctx.gh.get_issue(issue_number)
        except Exception as e:
            ctx.logger.error(f"Failed to retrieve issue #{issue_number}: {e}")
            await interaction.edit_original_response(content=f"❌ Could not retrieve issue #{issue_number}")
            return
        if difficulty:
            try:
                ctx.gh.replace_prefixed_label(issue, "Difficulty: ", difficulty)
            except Exception as e:
                ctx.logger.error(f"Failed to set labels for issue #{issue.number}: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to update difficulty for challenge [#{issue.number}]({issue.html_url}).")
                return
            await interaction.edit_original_response(content=f"✅ Updated difficulty to {difficulty} for challenge [#{issue.number}]({issue.html_url})")
        else:
            await interaction.edit_original_response(content="No difficulty provided.")

    @app_commands.command(name="status", description="Update a challenge's status in the project.")
    @app_commands.describe(
        issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
        status="New status"
    )
    async def update_status(self, interaction: BotInteraction, status: str, issue_number: Optional[int] = None):
        await interaction.response.defer(thinking=True)
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return
        if await ctx.deny_if_github_disabled(interaction):
            return
        if not ctx.project_id:
            await interaction.edit_original_response(content="Project ID not set or could not be resolved. Command disabled.")
            return
        issue_number = await resolve_issue_or_reply(interaction, issue_number)
        if issue_number is None:
            return
        try:
            issue = ctx.gh.get_issue(issue_number)
            ok, err = ctx.gh.add_issue_to_project_and_set_status(issue.node_id, ctx.project_id, status_name=status or "Idea")
            if ok:
                await interaction.edit_original_response(content=f"✅ Updated status to {status or 'Idea'} for challenge [#{issue.number}]({issue.html_url})")
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
    async def update_category(self, interaction: BotInteraction, category: str, issue_number: Optional[int] = None):
        await interaction.response.defer(thinking=True)
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return
        if await ctx.deny_if_github_disabled(interaction):
            return
        issue_number = await resolve_issue_or_reply(interaction, issue_number)
        if issue_number is None:
            return
        try:
            issue = ctx.gh.get_issue(issue_number)
        except Exception as e:
            ctx.logger.error(f"Failed to retrieve issue #{issue_number}: {e}")
            await interaction.edit_original_response(content=f"❌ Could not retrieve issue #{issue_number}")
            return
        if category:
            try:
                ctx.gh.replace_prefixed_label(issue, "Category: ", category)
            except Exception as e:
                ctx.logger.error(f"Failed to set labels for issue #{issue.number}: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to update category for challenge [#{issue.number}]({issue.html_url}).")
                return
            await interaction.edit_original_response(content=f"✅ Updated category to {category} for challenge [#{issue.number}]({issue.html_url})")
        else:
            await interaction.edit_original_response(content="No category provided.")

    @app_commands.command(name="name", description="Update a challenge's name (issue title).")
    @app_commands.describe(
        issue_number="GitHub issue number for the challenge (optional if used in mapped channel)",
        name="New name for the challenge"
    )
    async def update_name(self, interaction: BotInteraction, name: str, issue_number: Optional[int] = None):
        await interaction.response.defer(thinking=True)
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return
        if await ctx.deny_if_github_disabled(interaction):
            return
        issue_number = await resolve_issue_or_reply(interaction, issue_number)
        if issue_number is None:
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
