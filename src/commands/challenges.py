from typing import Optional

import discord
from discord import app_commands

from utils import CommandContext


def register_challenges_command(tree: app_commands.CommandTree, ctx: CommandContext) -> None:
    @tree.command(name="challenges", description="List challenges in the GitHub.")
    @app_commands.describe(
        status="Show all, open (non-finished), or closed (finished) challenges.",
        page="Page number to display (default: 1)")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="All", value="all"),
            app_commands.Choice(name="Open (non-finished)", value="open"),
            app_commands.Choice(name="Closed (finished)", value="closed"),
        ])
    async def issues(interaction: discord.Interaction, status: app_commands.Choice[str], page: Optional[int] = 1):
        await interaction.response.defer(thinking=True)
        if not ctx.is_authorized(interaction):
            await interaction.edit_original_response(content=ctx.unauthorized_message())
            return
        if not ctx.github_enabled:
            await interaction.edit_original_response(content="GitHub API features are disabled.")
            return
        
        if not ctx.gh_repo:
            await interaction.edit_original_response(content="GitHub repository not set or could not be resolved. Command disabled.")
            return
        
        ctx.logger.info(f"Fetching {status.name} challenges from GitHub repository {ctx.gh_repo.full_name}")
        if status.value == "open":
            issues = ctx.gh_repo.get_issues(state="open", labels=['Challenge'])
        elif status.value == "closed":
            issues = ctx.gh_repo.get_issues(state="closed", labels=['Challenge'])
        else:
            issues = ctx.gh_repo.get_issues(state="all", labels=['Challenge'])
            
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
        msg += f"\n\n[View all issues]({ctx.gh_repo.html_url}/issues)"
        await interaction.edit_original_response(content=msg)
