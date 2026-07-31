"""Cog for /challenges command to list GitHub challenges."""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


class ChallengesCog(commands.Cog):
    """Cog for listing challenges from GitHub."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Extend the static all/open/closed choices with the configured project board statuses.
        ctx = self.bot.command_context
        base_choices = self.challenges._params["status"].choices
        self.challenges._params["status"].choices = base_choices + [app_commands.Choice(name=s, value=s) for s in ctx.statuses]

    @app_commands.command(name="challenges", description="List challenges in the GitHub.")
    @app_commands.describe(
        status="Show all, open (non-finished), closed (finished), or filter by project board status.",
        page="Page number to display (default: 1)")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="All", value="all"),
            app_commands.Choice(name="Open (non-finished)", value="open"),
            app_commands.Choice(name="Closed (finished)", value="closed"),
        ])
    async def challenges(self, interaction: discord.Interaction, status: app_commands.Choice[str], page: Optional[int] = 1):
        """List challenges from GitHub, optionally filtered by status with pagination."""
        await interaction.response.defer(thinking=True)
        ctx = self.bot.command_context

        if await ctx.deny_if_unauthorized(interaction):
            return
        if await ctx.deny_if_github_disabled(interaction):
            return

        if not ctx.gh_repo:
            await interaction.edit_original_response(content="GitHub repository not set or could not be resolved. Command disabled.")
            return

        ctx.logger.info(f"Fetching {status.name} challenges from GitHub repository {ctx.gh_repo.full_name}")
        if status.value in ("all", "open", "closed"):
            state = "all" if status.value == "all" else status.value
            raw_issues = ctx.gh_repo.get_issues(state=state, labels=['Challenge'])
            items = [{"title": issue.title, "url": issue.html_url} for issue in raw_issues if "/issues/" in issue.html_url]
        else:
            if not ctx.project_id:
                await interaction.edit_original_response(content="GitHub project board not configured. Status filtering is disabled.")
                return
            try:
                # Project items are assumed to already be challenges, no extra label filter needed here.
                items = ctx.gh.get_issues_by_status(ctx.project_id, status.value)
            except Exception as e:
                ctx.logger.error(f"Failed to fetch {status.value} challenges: {e}")
                await interaction.edit_original_response(content=f"❌ Failed to fetch {status.value} challenges. Please contact an admin.")
                return

        if not items:
            await interaction.edit_original_response(content="No challenges found for this filter.")
            return

        # Pagination logic
        items_per_page = 10
        total_pages = (len(items) + items_per_page - 1) // items_per_page  # Ceiling division

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
        page_items = items[start_idx:end_idx]
        rows = [f"• [{item['title']}]({item['url']})" for item in page_items]

        msg = f"Challenges ({status.name}) - Page {page}/{total_pages}:\n" + "\n".join(rows)
        msg += f"\n\n[View all issues]({ctx.gh_repo.html_url}/issues)"
        await interaction.edit_original_response(content=msg)


async def setup(bot):
    """Load this cog into the bot."""
    await bot.add_cog(ChallengesCog(bot))
