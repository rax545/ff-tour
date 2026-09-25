import discord
from discord.ext import commands
from discord import app_commands

from config import SERVER_NAME
from database.db import connect
from utils.embeds import base, ok, err


class Support(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket", description="Create private esports support ticket")
    @app_commands.describe(ticket_type="registration / payment / match / report / general")
    async def ticket(self, interaction: discord.Interaction, ticket_type: str):
        g = interaction.guild
        if not g:
            return await interaction.response.send_message(
                embed=err("This command can only be used inside a server."),
                ephemeral=True
            )

        overwrites = {
            g.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True
            ),
            g.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                embed_links=True
            )
        }

        cat = discord.utils.get(g.categories, name="ESPORTS TICKETS")
        if not cat:
            cat = await g.create_category("ESPORTS TICKETS")

        clean_user = interaction.user.name.lower().replace(" ", "-")[:16]
        ch = await g.create_text_channel(
            f"ticket-{clean_user}",
            category=cat,
            overwrites=overwrites
        )

        db = await connect()
        cur = await db.execute(
            "INSERT INTO tickets(channel_id, opener_id, type) VALUES(?, ?, ?)",
            (ch.id, interaction.user.id, ticket_type)
        )
        tid = cur.lastrowid
        await db.commit()
        await db.close()

        ticket_embed = base(
            f"🎫 {SERVER_NAME} • TICKET #{tid}",
            (
                f"```fix\n"
                f"CATEGORY: {ticket_type.upper()}\n"
                f"```\n"
                f"Welcome {interaction.user.mention}!\n\n"
                f"Please describe your inquiry or issue below.\n"
                f"• Team Name & Tournament ID (if applicable)\n"
                f"• Screenshots or transaction details (for payments/results)\n\n"
                f"A **{SERVER_NAME}** staff member will assist you shortly."
            ),
            color=discord.Color.from_rgb(59, 130, 246)
        )
        ticket_embed.set_footer(text=f"🐺 {SERVER_NAME} • Support Desk")
        await ch.send(content=f"{interaction.user.mention} Staff has been alerted.", embed=ticket_embed)

        await interaction.response.send_message(
            embed=ok(f"Your support ticket has been created: {ch.mention}"),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Support(bot))
