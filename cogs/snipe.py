"""
Sistema de Snipe + comando !help / /help personalizado.
"""

import datetime
import discord
from discord import app_commands
from discord.ext import commands

import storage

_snipe_cache: dict[int, dict] = {}


class Snipe(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not message.content and not message.attachments:
            return

        _snipe_cache[message.channel.id] = {
            "content": message.content or "",
            "author_id": message.author.id,
            "author_name": str(message.author),
            "author_avatar": message.author.display_avatar.url,
            "created_at": message.created_at,
            "attachments": [a.url for a in message.attachments],
            "channel_id": message.channel.id,
            "channel_name": message.channel.name,
        }

        snipe_channel_id = storage.get_snipe_channel(message.guild.id)
        if not snipe_channel_id:
            return
        snipe_channel = message.guild.get_channel(snipe_channel_id)
        if not snipe_channel:
            return
        try:
            await snipe_channel.send(embed=_build_snipe_embed(_snipe_cache[message.channel.id], message.channel, auto_log=True))
        except (discord.Forbidden, discord.HTTPException):
            pass

    @app_commands.command(name="setsnipe", description="Configura el canal de log de mensajes eliminados")
    @app_commands.describe(canal="Canal destino (vacío = desactivar)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setsnipe(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        if canal:
            storage.set_snipe_channel(interaction.guild.id, canal.id)
            embed = discord.Embed(title="✅ Canal de Snipe Configurado",
                                  description=f"Los mensajes eliminados se enviarán a {canal.mention}.",
                                  color=discord.Color.green())
            embed.add_field(name="💡 Consejo", value="Usa `/snipe` para consultar el último eliminado de cualquier canal.")
        else:
            storage.set_snipe_channel(interaction.guild.id, None)
            embed = discord.Embed(title="❌ Snipe Desactivado",
                                  description="Ya no se registrarán mensajes eliminados automáticamente.",
                                  color=discord.Color.red())
        embed.set_footer(text=f"Configurado por {interaction.user.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="snipe", description="Muestra el último mensaje eliminado en un canal")
    @app_commands.describe(canal="Canal a consultar (por defecto: este canal)")
    @app_commands.checks.has_permissions(administrator=True)
    async def snipe(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        if not storage.get_snipe_channel(interaction.guild.id):
            embed = discord.Embed(
                title="⚙️ Canal de Snipe No Configurado",
                description="Para usar `/snipe` primero configura el canal de log:\n\n"
                            "> `/setsnipe #canal`\n\n"
                            "A partir de entonces todos los mensajes eliminados quedarán registrados.",
                color=discord.Color.gold(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        objetivo = canal or interaction.channel
        cached = _snipe_cache.get(objetivo.id)
        if not cached:
            embed = discord.Embed(
                description=f"🔍 No hay mensajes eliminados recientes en {objetivo.mention}.\n"
                            f"*(El cache se reinicia cuando el bot se reinicia)*",
                color=discord.Color.greyple(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(embed=_build_snipe_embed(cached, objetivo, auto_log=False))


def _build_snipe_embed(cached: dict, channel, *, auto_log: bool) -> discord.Embed:
    title = (f"🗑️ Mensaje eliminado en #{cached['channel_name']}"
             if auto_log else f"🗑️ Último eliminado en {channel.mention}")
    embed = discord.Embed(title=title, description=cached["content"] or "*Sin texto (solo adjuntos)*",
                          color=discord.Color.red(), timestamp=cached["created_at"])
    embed.set_author(name=cached["author_name"], icon_url=cached["author_avatar"])
    if cached["attachments"]:
        first = cached["attachments"][0]
        if any(first.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
            embed.set_image(url=first)
        else:
            embed.add_field(name=f"📎 Adjuntos ({len(cached['attachments'])})",
                            value="\n".join(cached["attachments"][:5]), inline=False)
    embed.set_footer(text=f"Autor: <@{cached['author_id']}>")
    return embed


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _build_help_embed(self, prefix: str, guild_icon=None) -> discord.Embed:
        embed = discord.Embed(
            title="📖 Todos los comandos",
            description=(
                f"Prefijo actual: **`{prefix}`**\n"
                f"Todos los comandos de moderación funcionan con **prefijo** (`{prefix}comando`) "
                f"y también como **slash** (`/comando`)."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow(),
        )
        if guild_icon:
            embed.set_thumbnail(url=guild_icon)

        embed.add_field(
            name=f"🛡️ Moderación  `{prefix}` · `/`",
            value=(
                f"`ban` `kick` `mute` `unmute`\n"
                f"`warn` `warns` `clearwarns`\n"
                f"`lock` `unlock` `clear`\n"
                f"`setprefix` `serverinfo`"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎫 Tickets  `/`",
            value="`/panelsetup` `/ticketnotify`",
            inline=True,
        )
        embed.add_field(
            name="⚙️ Configuración  `/`",
            value="`/setrole` `/setlog` `/setalllog`\n`/clearlogs` `/keepalive` `/autorole`",
            inline=True,
        )
        embed.add_field(
            name="👋 Bienvenidas  `/`",
            value="`/setwelcome` `/setleave`\n`/testwelcome` `/testleave`",
            inline=True,
        )
        embed.add_field(
            name="🎁 Giveaways  `/`",
            value="`/giveaway` `/giveaways`",
            inline=True,
        )
        embed.add_field(
            name="👤 Usuarios  `/`",
            value="`/userinfo`",
            inline=True,
        )
        embed.add_field(
            name="✨ Features  `/`",
            value="`/poll` `/reactionrole`",
            inline=True,
        )
        embed.add_field(
            name="🗑️ Snipe  `/`  *(solo admins)*",
            value="`/snipe` `/setsnipe`",
            inline=True,
        )
        embed.add_field(
            name="🔗 Webhooks  `/`",
            value="`/webhookcreate` `/webhookdelete`",
            inline=True,
        )
        embed.set_footer(text=f"Usa {prefix}help <comando> para ver detalles de un comando de prefijo")
        return embed

    @commands.command(name="help", aliases=["h", "ayuda"], help="📖 Muestra este menú de ayuda")
    async def help_prefix(self, ctx: commands.Context):
        prefix = storage.get_prefix(ctx.guild.id) if ctx.guild else "!"
        icon = ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None
        await ctx.send(embed=self._build_help_embed(prefix, icon))

    @app_commands.command(name="help", description="📖 Muestra todos los comandos disponibles")
    async def help_slash(self, interaction: discord.Interaction):
        prefix = storage.get_prefix(interaction.guild.id) if interaction.guild else "!"
        icon = interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None
        await interaction.response.send_message(embed=self._build_help_embed(prefix, icon))


async def setup(bot: commands.Bot):
    await bot.add_cog(Snipe(bot))
    await bot.add_cog(Help(bot))
