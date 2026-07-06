"""
Comandos de moderación — disponibles por prefijo (!comando) y slash (/comando):
ban, kick, mute, unmute, warn, warns, clearwarns, lock, unlock, clear, setprefix
"""

import re
import datetime
import discord
from discord import app_commands
from discord.ext import commands

import storage


# ------------------------------------------------------------------ checks
def can_use_mod_commands():
    """Check para comandos de prefijo: Admin O Staff role."""
    async def predicate(ctx: commands.Context):
        if ctx.author.guild_permissions.administrator:
            return True
        staff_role_id = storage.get_staff_role(ctx.guild.id)
        if staff_role_id:
            role = ctx.guild.get_role(staff_role_id)
            if role and role in ctx.author.roles:
                return True
        raise commands.MissingPermissions(["administrator"])
    return commands.check(predicate)


def mod_slash_check():
    """Check para slash commands: Admin O Staff role."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        staff_role_id = storage.get_staff_role(interaction.guild.id)
        if staff_role_id:
            role = interaction.guild.get_role(staff_role_id)
            if role and role in interaction.user.roles:
                return True
        raise app_commands.MissingPermissions(["administrator"])
    return app_commands.check(predicate)


# ------------------------------------------------------------------ helpers
async def send_log(guild: discord.Guild, log_type: str, embed: discord.Embed):
    channel_id = storage.get_log_channel(guild.id, log_type)
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel and channel.permissions_for(guild.me).send_messages:
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


def parse_duration(texto: str):
    match = re.fullmatch(r"(\d+)([smhd])", texto.lower().strip())
    if not match:
        return None
    cantidad, unidad = match.groups()
    cantidad = int(cantidad)
    return {
        "s": datetime.timedelta(seconds=cantidad),
        "m": datetime.timedelta(minutes=cantidad),
        "h": datetime.timedelta(hours=cantidad),
        "d": datetime.timedelta(days=cantidad),
    }[unidad]


def safe_thumbnail(embed: discord.Embed, member: discord.Member):
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)


# ------------------------------------------------------------------ cog
class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ================================================================
    # LOCK / UNLOCK
    # ================================================================

    @commands.command(name="lock", help="🔒 Bloquea un canal. Uso: !lock [#canal]")
    @can_use_mod_commands()
    async def lock_prefix(self, ctx: commands.Context, canal: discord.TextChannel = None):
        canal = canal or ctx.channel
        ow = canal.overwrites_for(ctx.guild.default_role)
        ow.send_messages = False
        await canal.set_permissions(ctx.guild.default_role, overwrite=ow, reason=f"Bloqueado por {ctx.author}")
        embed = discord.Embed(title="🔒 Canal Bloqueado", description=f"{canal.mention} ha sido bloqueado.",
                              color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {ctx.author.name}")
        await ctx.send(embed=embed)
        if canal.id != ctx.channel.id:
            try: await canal.send(embed=embed)
            except discord.Forbidden: pass
        await send_log(ctx.guild, "locks", embed)

    @app_commands.command(name="lock", description="🔒 Bloquea un canal para que nadie pueda escribir")
    @app_commands.describe(canal="Canal a bloquear (por defecto: este canal)")
    @mod_slash_check()
    async def lock_slash(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        objetivo = canal or interaction.channel
        ow = objetivo.overwrites_for(interaction.guild.default_role)
        ow.send_messages = False
        await objetivo.set_permissions(interaction.guild.default_role, overwrite=ow, reason=f"Bloqueado por {interaction.user}")
        embed = discord.Embed(title="🔒 Canal Bloqueado", description=f"{objetivo.mention} ha sido bloqueado.",
                              color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
        if objetivo.id != interaction.channel.id:
            try: await objetivo.send(embed=embed)
            except discord.Forbidden: pass
        await send_log(interaction.guild, "locks", embed)

    @commands.command(name="unlock", help="🔓 Desbloquea un canal. Uso: !unlock [#canal]")
    @can_use_mod_commands()
    async def unlock_prefix(self, ctx: commands.Context, canal: discord.TextChannel = None):
        canal = canal or ctx.channel
        ow = canal.overwrites_for(ctx.guild.default_role)
        ow.send_messages = None
        await canal.set_permissions(ctx.guild.default_role, overwrite=ow, reason=f"Desbloqueado por {ctx.author}")
        embed = discord.Embed(title="🔓 Canal Desbloqueado", description=f"{canal.mention} ha sido desbloqueado.",
                              color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {ctx.author.name}")
        await ctx.send(embed=embed)
        if canal.id != ctx.channel.id:
            try: await canal.send(embed=embed)
            except discord.Forbidden: pass
        await send_log(ctx.guild, "locks", embed)

    @app_commands.command(name="unlock", description="🔓 Desbloquea un canal para que todos puedan escribir")
    @app_commands.describe(canal="Canal a desbloquear (por defecto: este canal)")
    @mod_slash_check()
    async def unlock_slash(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        objetivo = canal or interaction.channel
        ow = objetivo.overwrites_for(interaction.guild.default_role)
        ow.send_messages = None
        await objetivo.set_permissions(interaction.guild.default_role, overwrite=ow, reason=f"Desbloqueado por {interaction.user}")
        embed = discord.Embed(title="🔓 Canal Desbloqueado", description=f"{objetivo.mention} ha sido desbloqueado.",
                              color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
        if objetivo.id != interaction.channel.id:
            try: await objetivo.send(embed=embed)
            except discord.Forbidden: pass
        await send_log(interaction.guild, "locks", embed)

    # ================================================================
    # BAN
    # ================================================================

    @commands.command(name="ban", help="🔨 Banea a un usuario. Uso: !ban @usuario [razón]")
    @can_use_mod_commands()
    async def ban_prefix(self, ctx: commands.Context, miembro: discord.Member, *, razon: str = "No especificada"):
        if miembro.guild_permissions.administrator:
            await ctx.send("❌ No puedes banear a un administrador."); return
        if miembro.id == ctx.author.id:
            await ctx.send("❌ No puedes banearte a ti mismo."); return
        await miembro.ban(reason=f"{razon} | Moderador: {ctx.author}", delete_message_seconds=0)
        embed = self._ban_embed(miembro, razon, ctx.author, ctx.guild)
        await ctx.send(embed=embed)
        await send_log(ctx.guild, "bans", embed)

    @app_commands.command(name="ban", description="🔨 Banea a un usuario del servidor")
    @app_commands.describe(usuario="Usuario a banear", razon="Razón del ban")
    @mod_slash_check()
    async def ban_slash(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        if usuario.guild_permissions.administrator:
            await interaction.response.send_message("❌ No puedes banear a un administrador.", ephemeral=True); return
        if usuario.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes banearte a ti mismo.", ephemeral=True); return
        await usuario.ban(reason=f"{razon} | Moderador: {interaction.user}", delete_message_seconds=0)
        embed = self._ban_embed(usuario, razon, interaction.user, interaction.guild)
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, "bans", embed)

    def _ban_embed(self, miembro, razon, moderador, guild):
        e = discord.Embed(title="🔨 Usuario Baneado", color=discord.Color.dark_red(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="👤 Usuario", value=f"{miembro} (`{miembro.id}`)", inline=False)
        e.add_field(name="📝 Razón", value=razon, inline=False)
        e.add_field(name="🛡️ Moderador", value=moderador.mention, inline=False)
        safe_thumbnail(e, miembro)
        e.set_footer(text=guild.name)
        return e

    # ================================================================
    # KICK
    # ================================================================

    @commands.command(name="kick", help="👢 Expulsa a un usuario. Uso: !kick @usuario [razón]")
    @can_use_mod_commands()
    async def kick_prefix(self, ctx: commands.Context, miembro: discord.Member, *, razon: str = "No especificada"):
        if miembro.guild_permissions.administrator:
            await ctx.send("❌ No puedes expulsar a un administrador."); return
        if miembro.id == ctx.author.id:
            await ctx.send("❌ No puedes expulsarte a ti mismo."); return
        await miembro.kick(reason=f"{razon} | Moderador: {ctx.author}")
        embed = self._kick_embed(miembro, razon, ctx.author, ctx.guild)
        await ctx.send(embed=embed)
        await send_log(ctx.guild, "kicks", embed)

    @app_commands.command(name="kick", description="👢 Expulsa a un usuario del servidor")
    @app_commands.describe(usuario="Usuario a expulsar", razon="Razón de la expulsión")
    @mod_slash_check()
    async def kick_slash(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        if usuario.guild_permissions.administrator:
            await interaction.response.send_message("❌ No puedes expulsar a un administrador.", ephemeral=True); return
        if usuario.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes expulsarte a ti mismo.", ephemeral=True); return
        await usuario.kick(reason=f"{razon} | Moderador: {interaction.user}")
        embed = self._kick_embed(usuario, razon, interaction.user, interaction.guild)
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, "kicks", embed)

    def _kick_embed(self, miembro, razon, moderador, guild):
        e = discord.Embed(title="👢 Usuario Expulsado", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="👤 Usuario", value=f"{miembro} (`{miembro.id}`)", inline=False)
        e.add_field(name="📝 Razón", value=razon, inline=False)
        e.add_field(name="🛡️ Moderador", value=moderador.mention, inline=False)
        safe_thumbnail(e, miembro)
        e.set_footer(text=guild.name)
        return e

    # ================================================================
    # MUTE / UNMUTE
    # ================================================================

    @commands.command(name="mute", help="🔇 Silencia. Uso: !mute @usuario [10m/2h/1d] [razón]")
    @can_use_mod_commands()
    async def mute_prefix(self, ctx: commands.Context, miembro: discord.Member, tiempo: str = "10m", *, razon: str = "No especificada"):
        if miembro.guild_permissions.administrator:
            await ctx.send("❌ No puedes mutear a un administrador."); return
        if miembro.id == ctx.author.id:
            await ctx.send("❌ No puedes mutearte a ti mismo."); return
        duracion = parse_duration(tiempo)
        if duracion is None:
            await ctx.send("⚠️ Formato inválido. Usa: `10m`, `2h`, `1d`, `30s`"); return
        await miembro.timeout(duracion, reason=f"{razon} | Moderador: {ctx.author}")
        embed = self._mute_embed(miembro, tiempo, razon, ctx.author, ctx.guild)
        await ctx.send(embed=embed)
        await send_log(ctx.guild, "mutes", embed)

    @app_commands.command(name="mute", description="🔇 Silencia a un usuario temporalmente")
    @app_commands.describe(usuario="Usuario a silenciar", duracion="Duración: 10m, 2h, 1d, 30s", razon="Razón del mute")
    @mod_slash_check()
    async def mute_slash(self, interaction: discord.Interaction, usuario: discord.Member, duracion: str = "10m", razon: str = "No especificada"):
        if usuario.guild_permissions.administrator:
            await interaction.response.send_message("❌ No puedes mutear a un administrador.", ephemeral=True); return
        if usuario.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes mutearte a ti mismo.", ephemeral=True); return
        td = parse_duration(duracion)
        if td is None:
            await interaction.response.send_message("⚠️ Formato inválido. Usa: `10m`, `2h`, `1d`, `30s`", ephemeral=True); return
        await usuario.timeout(td, reason=f"{razon} | Moderador: {interaction.user}")
        embed = self._mute_embed(usuario, duracion, razon, interaction.user, interaction.guild)
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, "mutes", embed)

    def _mute_embed(self, miembro, tiempo, razon, moderador, guild):
        e = discord.Embed(title="🔇 Usuario Silenciado", color=discord.Color.dark_gray(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="👤 Usuario", value=f"{miembro} (`{miembro.id}`)", inline=False)
        e.add_field(name="⏱️ Duración", value=tiempo, inline=False)
        e.add_field(name="📝 Razón", value=razon, inline=False)
        e.add_field(name="🛡️ Moderador", value=moderador.mention, inline=False)
        safe_thumbnail(e, miembro)
        e.set_footer(text=guild.name)
        return e

    @commands.command(name="unmute", help="🔊 Dessilencia. Uso: !unmute @usuario")
    @can_use_mod_commands()
    async def unmute_prefix(self, ctx: commands.Context, miembro: discord.Member):
        await miembro.timeout(None, reason=f"Desmuteado por {ctx.author}")
        embed = discord.Embed(title="🔊 Usuario Dessilenciado", description=f"{miembro.mention} ha sido desmuteado.",
                              color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {ctx.author.name}")
        await ctx.send(embed=embed)
        await send_log(ctx.guild, "mutes", embed)

    @app_commands.command(name="unmute", description="🔊 Quita el silencio a un usuario")
    @app_commands.describe(usuario="Usuario a dessilenciar")
    @mod_slash_check()
    async def unmute_slash(self, interaction: discord.Interaction, usuario: discord.Member):
        await usuario.timeout(None, reason=f"Desmuteado por {interaction.user}")
        embed = discord.Embed(title="🔊 Usuario Dessilenciado", description=f"{usuario.mention} ha sido desmuteado.",
                              color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, "mutes", embed)

    # ================================================================
    # WARN
    # ================================================================

    @commands.command(name="warn", help="⚠️ Advierte. Uso: !warn @usuario [razón]")
    @can_use_mod_commands()
    async def warn_prefix(self, ctx: commands.Context, miembro: discord.Member, *, razon: str = "No especificada"):
        if miembro.id == ctx.author.id:
            await ctx.send("❌ No puedes advertirte a ti mismo."); return
        embed, auto_embed = await self._apply_warn(ctx.guild, miembro, razon, ctx.author)
        await ctx.send(embed=embed)
        await send_log(ctx.guild, "warns", embed)
        if auto_embed:
            await ctx.send(embed=auto_embed[0])
            await send_log(ctx.guild, auto_embed[1], auto_embed[0])

    @app_commands.command(name="warn", description="⚠️ Advierte a un usuario y registra la advertencia")
    @app_commands.describe(usuario="Usuario a advertir", razon="Razón de la advertencia")
    @mod_slash_check()
    async def warn_slash(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        if usuario.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes advertirte a ti mismo.", ephemeral=True); return
        embed, auto_embed = await self._apply_warn(interaction.guild, usuario, razon, interaction.user)
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, "warns", embed)
        if auto_embed:
            await interaction.followup.send(embed=auto_embed[0])
            await send_log(interaction.guild, auto_embed[1], auto_embed[0])

    async def _apply_warn(self, guild, miembro, razon, moderador):
        """Aplica el warn y devuelve (embed_warn, (embed_castigo, log_type) | None)."""
        storage.add_warn(guild.id, miembro.id, razon, moderador.id)
        warns = storage.get_warns(guild.id, miembro.id)
        total = len(warns)

        embed = discord.Embed(title="⚠️ Advertencia Registrada", color=discord.Color.gold(), timestamp=datetime.datetime.utcnow())
        embed.add_field(name="👤 Usuario", value=f"{miembro} (`{miembro.id}`)", inline=False)
        embed.add_field(name="📝 Razón", value=razon, inline=False)
        embed.add_field(name="📊 Total Warns", value=f"**{total}** ⚠️", inline=False)
        safe_thumbnail(embed, miembro)
        embed.set_footer(text=f"Moderador: {moderador.name}")

        # DM al usuario
        try:
            dm = discord.Embed(title="⚠️ Advertencia Recibida",
                               description=f"Has recibido una advertencia en **{guild.name}**.\nRazón: {razon}",
                               color=discord.Color.gold())
            dm.add_field(name="Total de Warns", value=f"{total}/7")
            if total >= 3:
                dm.add_field(name="⚠️", value="Con más warns se aplicarán castigos automáticos.")
            await miembro.send(embed=dm)
        except discord.Forbidden:
            pass

        # Auto-castigos
        auto = None
        if total == 3:
            try:
                await miembro.timeout(datetime.timedelta(hours=1), reason="Auto-castigo por 3 warns")
                a = discord.Embed(title="🤖 Auto-Mute por 3 warns",
                                  description=f"{miembro.mention} silenciado 1h automáticamente.",
                                  color=discord.Color.dark_gray(), timestamp=datetime.datetime.utcnow())
                auto = (a, "mutes")
            except discord.Forbidden:
                pass
        elif total == 5:
            try:
                await miembro.kick(reason="Auto-castigo por 5 warns")
                a = discord.Embed(title="🤖 Auto-Kick por 5 warns",
                                  description=f"{miembro} expulsado automáticamente.",
                                  color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
                auto = (a, "kicks")
            except discord.Forbidden:
                pass
        elif total == 7:
            try:
                await miembro.ban(reason="Auto-castigo por 7 warns", delete_message_seconds=0)
                a = discord.Embed(title="🤖 Auto-Ban por 7 warns",
                                  description=f"{miembro} baneado automáticamente.",
                                  color=discord.Color.dark_red(), timestamp=datetime.datetime.utcnow())
                auto = (a, "bans")
            except discord.Forbidden:
                pass

        return embed, auto

    @commands.command(name="warns", help="📊 Ver advertencias. Uso: !warns @usuario")
    async def warns_prefix(self, ctx: commands.Context, miembro: discord.Member):
        embed = self._warns_embed(ctx.guild, miembro)
        await ctx.send(embed=embed)

    @app_commands.command(name="warns", description="📊 Ver las advertencias de un usuario")
    @app_commands.describe(usuario="Usuario a consultar")
    async def warns_slash(self, interaction: discord.Interaction, usuario: discord.Member):
        embed = self._warns_embed(interaction.guild, usuario)
        await interaction.response.send_message(embed=embed)

    def _warns_embed(self, guild, miembro):
        lista = storage.get_warns(guild.id, miembro.id)
        if not lista:
            return discord.Embed(description=f"✅ {miembro.mention} no tiene advertencias.", color=discord.Color.green())
        embed = discord.Embed(title=f"⚠️ Advertencias de {miembro.name}", color=discord.Color.gold())
        safe_thumbnail(embed, miembro)
        for i, w in enumerate(lista, 1):
            embed.add_field(name=f"#{i}",
                            value=f"**Razón:** {w['reason']}\n**Moderador:** <@{w['moderator']}>\n**Fecha:** {w['date']}",
                            inline=False)
        embed.set_footer(text=f"Total: {len(lista)} warns")
        return embed

    @commands.command(name="clearwarns", help="🧹 Limpia advertencias. Uso: !clearwarns @usuario")
    @can_use_mod_commands()
    async def clearwarns_prefix(self, ctx: commands.Context, miembro: discord.Member):
        storage.clear_warns(ctx.guild.id, miembro.id)
        embed = discord.Embed(title="🧹 Advertencias Limpiadas",
                              description=f"Se eliminaron todas las advertencias de {miembro.mention}.",
                              color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {ctx.author.name}")
        await ctx.send(embed=embed)
        await send_log(ctx.guild, "warns", embed)

    @app_commands.command(name="clearwarns", description="🧹 Elimina todas las advertencias de un usuario")
    @app_commands.describe(usuario="Usuario al que limpiar los warns")
    @mod_slash_check()
    async def clearwarns_slash(self, interaction: discord.Interaction, usuario: discord.Member):
        storage.clear_warns(interaction.guild.id, usuario.id)
        embed = discord.Embed(title="🧹 Advertencias Limpiadas",
                              description=f"Se eliminaron todas las advertencias de {usuario.mention}.",
                              color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, "warns", embed)

    # ================================================================
    # CLEAR
    # ================================================================

    @commands.command(name="clear", aliases=["purge", "limpiar"], help="🧹 Elimina mensajes. Uso: !clear [cantidad]")
    @can_use_mod_commands()
    async def clear_prefix(self, ctx: commands.Context, cantidad: int = 5):
        cantidad = max(1, min(cantidad, 100))
        eliminados = await ctx.channel.purge(limit=cantidad + 1)
        embed = discord.Embed(title="🧹 Mensajes Eliminados",
                              description=f"Se han eliminado **{len(eliminados) - 1}** mensajes.",
                              color=discord.Color.gold(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {ctx.author.name}")
        aviso = await ctx.send(embed=embed)
        await aviso.delete(delay=3)

    @app_commands.command(name="clear", description="🧹 Elimina una cantidad de mensajes del canal")
    @app_commands.describe(cantidad="Número de mensajes a eliminar (1-100, por defecto 5)")
    @mod_slash_check()
    async def clear_slash(self, interaction: discord.Interaction, cantidad: int = 5):
        cantidad = max(1, min(cantidad, 100))
        await interaction.response.defer(ephemeral=True)
        eliminados = await interaction.channel.purge(limit=cantidad)
        embed = discord.Embed(title="🧹 Mensajes Eliminados",
                              description=f"Se han eliminado **{len(eliminados)}** mensajes.",
                              color=discord.Color.gold(), timestamp=datetime.datetime.utcnow())
        embed.set_footer(text=f"Moderador: {interaction.user.name}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ================================================================
    # SETPREFIX
    # ================================================================

    @commands.command(name="setprefix", help="🔧 Cambia el prefijo. Uso: !setprefix ?")
    @commands.has_permissions(administrator=True)
    async def setprefix_prefix(self, ctx: commands.Context, nuevo_prefijo: str):
        if len(nuevo_prefijo) > 5:
            await ctx.send("⚠️ El prefijo debe tener 5 caracteres o menos."); return
        storage.set_prefix(ctx.guild.id, nuevo_prefijo)
        embed = discord.Embed(title="✅ Prefijo Actualizado",
                              description=f"El nuevo prefijo es: **`{nuevo_prefijo}`**",
                              color=discord.Color.green())
        await ctx.send(embed=embed)

    @app_commands.command(name="setprefix", description="🔧 Cambia el prefijo de los comandos de texto")
    @app_commands.describe(prefijo="Nuevo prefijo (máximo 5 caracteres)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setprefix_slash(self, interaction: discord.Interaction, prefijo: str):
        if len(prefijo) > 5:
            await interaction.response.send_message("⚠️ El prefijo debe tener 5 caracteres o menos.", ephemeral=True); return
        storage.set_prefix(interaction.guild.id, prefijo)
        embed = discord.Embed(title="✅ Prefijo Actualizado",
                              description=f"El nuevo prefijo es: **`{prefijo}`**",
                              color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================================================================
    # USERINFO
    # ================================================================

    @app_commands.command(name="userinfo", description="👤 Ver información detallada de un usuario")
    @app_commands.describe(usuario="El usuario a consultar (por defecto eres tú)")
    async def userinfo(self, interaction: discord.Interaction, usuario: discord.Member = None):
        member = usuario or interaction.user
        warns = storage.get_warns(interaction.guild.id, member.id)
        roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]

        color = member.color if member.color.value != 0 else discord.Color.blurple()
        embed = discord.Embed(title=f"👤 {member.display_name}", color=color, timestamp=datetime.datetime.utcnow())
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        try:
            full_user = await interaction.client.fetch_user(member.id)
            if full_user.banner:
                embed.set_image(url=full_user.banner.url)
        except Exception:
            pass

        embed.add_field(name="🏷️ Tag", value=str(member), inline=True)
        embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="🤖 Bot", value="Sí" if member.bot else "No", inline=True)
        embed.add_field(name="📅 Cuenta creada",
                        value=f"<t:{int(member.created_at.timestamp())}:D>\n<t:{int(member.created_at.timestamp())}:R>",
                        inline=True)
        embed.add_field(name="📥 Entró al servidor",
                        value=f"<t:{int(member.joined_at.timestamp())}:D>\n<t:{int(member.joined_at.timestamp())}:R>",
                        inline=True)
        embed.add_field(name="⚠️ Warns", value=f"**{len(warns)}** / 7", inline=True)

        status_icons = {
            discord.Status.online:  "🟢 En línea",
            discord.Status.idle:    "🟡 Ausente",
            discord.Status.dnd:     "🔴 No molestar",
            discord.Status.offline: "⚫ Desconectado",
        }
        embed.add_field(name="📶 Estado", value=status_icons.get(member.status, "⚫ Desconectado"), inline=True)

        if member.premium_since:
            embed.add_field(name="💎 Boosting desde",
                            value=f"<t:{int(member.premium_since.timestamp())}:R>", inline=True)

        if roles:
            roles_text = " ".join(roles[:20])
            if len(roles) > 20:
                roles_text += f"\n*+{len(roles) - 20} más...*"
            embed.add_field(name=f"🎭 Roles [{len(roles)}]", value=roles_text, inline=False)
        else:
            embed.add_field(name="🎭 Roles", value="Sin roles", inline=False)

        embed.set_footer(text=interaction.guild.name,
                         icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
