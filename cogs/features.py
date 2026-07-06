"""
Cog de features:
- !serverinfo / /serverinfo
- /poll
- /reactionrole
"""

import discord
from discord import app_commands
from discord.ext import commands
import datetime

import storage


class Features(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ================================================================
    # SERVERINFO
    # ================================================================

    def _serverinfo_embed(self, guild: discord.Guild) -> discord.Embed:
        bots = len([m for m in guild.members if m.bot])
        humanos = len(guild.members) - bots

        embed = discord.Embed(
            title=f"📊 {guild.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(
            name="👥 Miembros",
            value=f"**Total:** {guild.member_count}\n**Humanos:** {humanos}\n**Bots:** {bots}",
            inline=True,
        )
        embed.add_field(
            name="📅 Creación",
            value=f"<t:{int(guild.created_at.timestamp())}:F>",
            inline=True,
        )
        embed.add_field(
            name="🆔 IDs",
            value=f"**Servidor:** `{guild.id}`\n**Dueño:** {guild.owner.mention} (`{guild.owner.id}`)",
            inline=False,
        )
        embed.add_field(
            name="📁 Canales",
            value=f"**Texto:** {len(guild.text_channels)}\n**Voz:** {len(guild.voice_channels)}\n**Categorías:** {len(guild.categories)}",
            inline=True,
        )
        embed.add_field(
            name="🏷️ Roles",
            value=f"**Total:** {len(guild.roles)}\n**Con permisos:** {len([r for r in guild.roles if r.permissions.value > 0])}",
            inline=True,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Nivel de verificación: {guild.verification_level}")
        return embed

    @commands.command(name="serverinfo", aliases=["si", "info"], help="📊 Info del servidor")
    async def serverinfo_prefix(self, ctx: commands.Context):
        await ctx.send(embed=self._serverinfo_embed(ctx.guild))

    @app_commands.command(name="serverinfo", description="📊 Muestra información del servidor")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self._serverinfo_embed(interaction.guild))

    # ================================================================
    # AVATAR
    # ================================================================

    def _avatar_embed(self, member: discord.Member) -> discord.Embed:
        avatar = member.display_avatar
        embed = discord.Embed(
            title=f"🖼️ Avatar de {member.display_name}",
            color=member.color if member.color.value != 0 else discord.Color.blurple(),
        )
        embed.set_image(url=avatar.url)
        png  = avatar.replace(format="png",  size=4096).url
        jpg  = avatar.replace(format="jpg",  size=4096).url
        webp = avatar.replace(format="webp", size=4096).url
        embed.description = f"[PNG]({png}) · [JPG]({jpg}) · [WEBP]({webp})"
        embed.set_footer(text=f"ID: {member.id}")
        return embed

    @commands.command(name="avatar", aliases=["av", "pfp"], help="🖼️ Muestra el avatar de un usuario")
    async def avatar_prefix(self, ctx: commands.Context, miembro: discord.Member = None):
        member = miembro or ctx.author
        await ctx.send(embed=self._avatar_embed(member))

    @app_commands.command(name="avatar", description="🖼️ Muestra el avatar de un usuario en grande")
    @app_commands.describe(usuario="El usuario cuyo avatar quieres ver (por defecto: tú)")
    async def avatar_slash(self, interaction: discord.Interaction, usuario: discord.Member = None):
        member = usuario or interaction.user
        await interaction.response.send_message(embed=self._avatar_embed(member))

    # ================================================================
    # SETNSFW
    # ================================================================

    @app_commands.command(name="setnsfw", description="🔞 Activa o desactiva NSFW en un canal")
    @app_commands.describe(
        canal="Canal a modificar (por defecto: este canal)",
        activar="True = activar NSFW · False = desactivar",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setnsfw(self, interaction: discord.Interaction,
                      canal: discord.TextChannel = None, activar: bool = True):
        objetivo = canal or interaction.channel
        await objetivo.edit(nsfw=activar, reason=f"{'Activado' if activar else 'Desactivado'} por {interaction.user}")
        estado = "🔞 Activado" if activar else "✅ Desactivado"
        color  = discord.Color.red() if activar else discord.Color.green()
        embed  = discord.Embed(
            title=f"NSFW {estado}",
            description=(
                f"El canal {objetivo.mention} ahora es **{'NSFW' if activar else 'SFW'}**.\n\n"
                + ("⚠️ Solo usuarios mayores de 18 años deberían acceder a este canal."
                   if activar else "El canal volvió a ser seguro para todos los usuarios.")
            ),
            color=color,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(text=f"Configurado por {interaction.user.name}")
        await interaction.response.send_message(embed=embed)

    # ================================================================
    # REACTION ROLES
    # ================================================================

    @app_commands.command(name="reactionrole", description="Configura reaction roles")
    @app_commands.describe(
        accion="add (agregar) o remove (quitar)",
        mensaje_id="ID del mensaje",
        emoji="El emoji (ej: 🎮)",
        rol="El rol a asignar",
        canal="Canal donde está el mensaje (por defecto: este canal)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def reactionrole(
        self,
        interaction: discord.Interaction,
        accion: str,
        mensaje_id: str,
        emoji: str = None,
        rol: discord.Role = None,
        canal: discord.TextChannel = None,
    ):
        if accion.lower() not in ["add", "remove"]:
            await interaction.response.send_message("❌ Acción debe ser 'add' o 'remove'", ephemeral=True)
            return

        try:
            msg_id = int(mensaje_id)
        except ValueError:
            await interaction.response.send_message("❌ ID de mensaje inválido", ephemeral=True)
            return

        canal_objetivo = canal or interaction.channel

        try:
            message = await canal_objetivo.fetch_message(msg_id)
        except discord.NotFound:
            await interaction.response.send_message(
                f"❌ No encontré el mensaje en {canal_objetivo.mention}.\n"
                f"Si está en otro canal usa el parámetro `canal`.",
                ephemeral=True,
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message("❌ No tengo permisos para acceder a ese canal.", ephemeral=True)
            return

        if accion.lower() == "add":
            if not emoji or not rol:
                await interaction.response.send_message("❌ Para agregar necesitas emoji y rol", ephemeral=True)
                return
            storage.add_reaction_role(interaction.guild.id, msg_id, emoji, rol.id)
            try:
                await message.add_reaction(emoji)
            except discord.Forbidden:
                await interaction.response.send_message("❌ No tengo permisos para reaccionar.", ephemeral=True)
                return
            except discord.HTTPException:
                await interaction.response.send_message("❌ Emoji inválido o no puedo usarlo.", ephemeral=True)
                return
            embed = discord.Embed(title="✅ Reaction Role Agregado",
                                  description=f"Emoji: {emoji}\nRol: {rol.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            if emoji:
                storage.remove_reaction_role(interaction.guild.id, msg_id, emoji)
                try: await message.clear_reaction(emoji)
                except Exception: pass
                embed = discord.Embed(title="✅ Reaction Role Removido",
                                      description=f"Emoji: {emoji}", color=discord.Color.green())
            else:
                storage.remove_reaction_role(interaction.guild.id, msg_id)
                try: await message.clear_reactions()
                except Exception: pass
                embed = discord.Embed(title="✅ Todos los Reaction Roles Removidos",
                                      description="Se removieron todas las reaction roles del mensaje",
                                      color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        reaction_roles = storage.get_reaction_roles(guild.id, payload.message_id)
        emoji_str = str(payload.emoji)
        if emoji_str in reaction_roles:
            role = guild.get_role(reaction_roles[emoji_str])
            member = guild.get_member(payload.user_id)
            if role and member:
                try: await member.add_roles(role, reason="Reaction role")
                except discord.Forbidden: pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        reaction_roles = storage.get_reaction_roles(guild.id, payload.message_id)
        emoji_str = str(payload.emoji)
        if emoji_str in reaction_roles:
            role = guild.get_role(reaction_roles[emoji_str])
            member = guild.get_member(payload.user_id)
            if role and member:
                try: await member.remove_roles(role, reason="Reaction role removed")
                except discord.Forbidden: pass

    # ================================================================
    # POLLS
    # ================================================================

    @app_commands.command(name="poll", description="📊 Crea una encuesta con reacciones")
    @app_commands.describe(
        pregunta="La pregunta de la encuesta",
        opcion1="Primera opción", opcion2="Segunda opción",
        opcion3="Tercera opción (opcional)", opcion4="Cuarta opción (opcional)",
        opcion5="Quinta opción (opcional)",
    )
    async def poll(self, interaction: discord.Interaction, pregunta: str,
                   opcion1: str, opcion2: str,
                   opcion3: str = None, opcion4: str = None, opcion5: str = None):
        opciones = [o for o in [opcion1, opcion2, opcion3, opcion4, opcion5] if o]
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        embed = discord.Embed(title="📊 Encuesta", description=f"**{pregunta}**\n\n",
                              color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        for i, opcion in enumerate(opciones):
            embed.description += f"{emojis[i]} {opcion}\n"
        embed.set_footer(text=f"Creada por {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(opciones)):
            await msg.add_reaction(emojis[i])


async def setup(bot: commands.Bot):
    await bot.add_cog(Features(bot))
