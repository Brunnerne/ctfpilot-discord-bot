"""Cog for the /challenge command group and all subcommands."""

from typing import Optional

from discord import app_commands
from discord.ext import commands

from bot import BotInteraction
from store import Store
from utils import discord_clean, resolve_issue_or_reply

from .create import CreateGroup
from .update import UpdateGroup


class ChallengeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    challenge_group = app_commands.Group(name="challenge", description="Challenge management commands.")

    create_group = CreateGroup(parent=challenge_group)
    update_group = UpdateGroup(parent=challenge_group)

    @challenge_group.command(name="info", description="Show information about the current challenge")
    @app_commands.describe(issue_number="GitHub issue number for the challenge (optional if used in mapped channel)")
    async def info(self, interaction: BotInteraction, issue_number: Optional[int] = None):
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return
        await interaction.response.defer(thinking=True)
        issue_number = await resolve_issue_or_reply(interaction, issue_number)
        if issue_number is None:
            return
        try:
            issue = ctx.gh.get_issue(issue_number)
            # Extract fields
            name = issue.title
            assignees = ', '.join([a.login for a in issue.assignees]) if issue.assignees else 'None'
            labels = [l.name for l in issue.labels]
            difficulty = next((l.split(':',1)[1].strip() for l in labels if l.lower().startswith('difficulty:')), 'Unknown')
            category = next((l.split(':',1)[1].strip() for l in labels if l.lower().startswith('category:')), 'Unknown')
            global_status = 'Open' if issue.state == 'open' else 'Closed'
            # Try to get project status
            project_status = 'Unknown'
            if ctx.project_id:
                try:
                    project_status = ctx.gh.get_issue_project_status(issue.number, ctx.project_id, issue.node_id)
                except Exception as e:
                    ctx.logger.error(f"Error fetching project status: {e}")
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
                f"[View Repository]({ctx.gh.repo.html_url})\n"
            )
            await interaction.edit_original_response(content=info_msg)
        except Exception as e:
            ctx.logger.error(f"Failed to fetch issue info: {e}")
            await interaction.edit_original_response(content="❌ Failed to fetch challenge info. Please contact an admin.")

    @challenge_group.command(name="link_channel", description="Manually link an issue to this channel")
    @app_commands.describe(issue_number="GitHub issue number to link to this channel.")
    async def link_channel(self, interaction: BotInteraction, issue_number: int):
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return
        Store.set_challenge_key(str(interaction.channel_id), issue_number)
        await interaction.response.send_message(f"✅ Linked issue #{issue_number} to this channel.", ephemeral=True)

    @challenge_group.command(name="clear_channel", description="Clear the issue-channel mapping for this channel")
    async def clear_channel(self, interaction: BotInteraction):
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return
        mapping = Store.get_key("challenges", {}) or {}
        channel_id = str(interaction.channel_id)
        if channel_id in mapping:
            Store.delete_challenge_key(channel_id)
            await interaction.response.send_message("✅ Cleared issue-channel mapping for this channel.", ephemeral=True)
        else:
            await interaction.response.send_message("No issue linked to this channel.", ephemeral=True)
