"""
Sistema de Welcomes y Leaves:
- /setwelcome: configura mensaje de bienvenida
- /setleave: configura mensaje de despedida
- /testwelcome: prueba el mensaje de bienvenida
- /testleave: prueba el mensaje de despedida
"""

import discord
from discord import app_commands
from discord.ext import commands
import datetime

import storage


class WelcomeModal(discord.ui.Modal):
    titulo = discord.ui.TextInput(
        label="Título del embed",
        placeholder="¡Bienvenido al servidor!",
        max_length=256,
        required=True,
    )
    descripcion = discord.ui.TextInput(
        label="Descripción del embed",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe aquí la bienvenida...\n\nUsa {user} para el nombre\nUsa {mention} para mencionarlo",
        max_length=4000,
        required=True,
    )
    imagen_url = discord.ui.TextInput(
        label="URL de la imagen (opcional)",
        placeholder="https://ejemplo.com/imagen.png",
        max_length=500,
        required=False,
    )
    thumbnail_url = discord.ui.TextInput(
        label="URL del thumbnail (opcional)",
        placeholder="https://ejemplo.com/thumbnail.png",
        max_length=500,
        required=False,
    )

    def __init__(self, canal: discord.TextChannel, is_leave: bool = False):
        # Pasamos el título correctamente al constructor del Modal
        title = "Configurar Mensaje de Despedida" if is_leave else "Configurar Mensaje de Bienvenida"
        super().__init__(title=title)
        self.canal = canal
        self.is_leave = is_leave

    async def on_submit(self, interaction: discord.Interaction):
        imagen = str(self.imagen_url).strip() if self.imagen_url.value else None
        thumbnail = str(self.thumbnail_url).strip() if self.thumbnail_url.value else None

        config = {
            "enabled": True,
            "channel_id": self.canal.id,
            "title": str(self.titulo),
            "description": str(self.descripcion),
            "image_url": imagen or None,
            "thumbnail_url": thumbnail or None,
        }

        if self.is_leave:
            storage.set_leave_config(interaction.guild.id, config)
            tipo = "Despedida"
        else:
            storage.set_welcome_config(interaction.guild.id, config)
            tipo = "Bienvenida"

        embed = discord.Embed(
            title=f"✅ {tipo} Configurada",
            description=f"El mensaje se enviará en {self.canal.mention}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Welcomes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def crear_embed(self, titulo, descripcion, guild, user=None, imagen_url=None, thumbnail_url=None, is_leave=False):
        if user:
            descripcion = descripcion.replace("{user}", user.name)
            descripcion = descripcion.replace("{mention}", user.mention)

        embed = discord.Embed(
            title=titulo,
            description=descripcion,
            color=discord.Color.red() if is_leave else discord.Color.gold(),
            timestamp=datetime.datetime.utcnow(),
        )

        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)

        if imagen_url:
            embed.set_image(url=imagen_url)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        embed.set_footer(text=guild.name)
        return embed

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Autorole
        autorole_id = storage.get_autorole(member.guild.id)
        if autorole_id:
            autorole = member.guild.get_role(autorole_id)
            if autorole and autorole < member.guild.me.top_role:
                try:
                    await member.add_roles(autorole, reason="Autorole automático")
                except discord.Forbidden:
                    pass

        # Mensaje de bienvenida
        config = storage.get_welcome_config(member.guild.id)
        if not config or not config.get("enabled"):
            return
        canal = member.guild.get_channel(config.get("channel_id"))
        if not canal:
            return
        try:
            embed = self.crear_embed(
                config["title"], config["description"], member.guild, member,
                config.get("image_url"), config.get("thumbnail_url"),
            )
            await canal.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        config = storage.get_leave_config(member.guild.id)
        if not config or not config.get("enabled"):
            return
        canal = member.guild.get_channel(config.get("channel_id"))
        if not canal:
            return
        try:
            embed = self.crear_embed(
                config["title"], config["description"], member.guild, member,
                config.get("image_url"), config.get("thumbnail_url"), is_leave=True,
            )
            await canal.send(embed=embed)
        except discord.Forbidden:
            pass

    @app_commands.command(name="setwelcome", description="Configura el mensaje de bienvenida")
    @app_commands.describe(canal="Canal donde se enviarán los mensajes de bienvenida")
    @app_commands.checks.has_permissions(administrator=True)
    async def setwelcome(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await interaction.response.send_modal(WelcomeModal(canal, is_leave=False))

    @app_commands.command(name="setleave", description="Configura el mensaje de despedida")
    @app_commands.describe(canal="Canal donde se enviarán los mensajes de despedida")
    @app_commands.checks.has_permissions(administrator=True)
    async def setleave(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await interaction.response.send_modal(WelcomeModal(canal, is_leave=True))

    @app_commands.command(name="testwelcome", description="Prueba el mensaje de bienvenida")
    @app_commands.checks.has_permissions(administrator=True)
    async def testwelcome(self, interaction: discord.Interaction):
        config = storage.get_welcome_config(interaction.guild.id)
        if not config or not config.get("enabled"):
            await interaction.response.send_message(
                "❌ No hay bienvenida configurada. Usa `/setwelcome` primero.", ephemeral=True
            )
            return
        canal = interaction.guild.get_channel(config.get("channel_id"))
        if not canal:
            await interaction.response.send_message("❌ El canal configurado no existe.", ephemeral=True)
            return
        try:
            embed = self.crear_embed(
                config["title"], config["description"], interaction.guild, interaction.user,
                config.get("image_url"), config.get("thumbnail_url"),
            )
            await canal.send(embed=embed)
            resp = discord.Embed(description=f"✅ Mensaje de prueba enviado a {canal.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=resp, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sin permisos para enviar en ese canal.", ephemeral=True)

    @app_commands.command(name="testleave", description="Prueba el mensaje de despedida")
    @app_commands.checks.has_permissions(administrator=True)
    async def testleave(self, interaction: discord.Interaction):
        config = storage.get_leave_config(interaction.guild.id)
        if not config or not config.get("enabled"):
            await interaction.response.send_message(
                "❌ No hay despedida configurada. Usa `/setleave` primero.", ephemeral=True
            )
            return
        canal = interaction.guild.get_channel(config.get("channel_id"))
        if not canal:
            await interaction.response.send_message("❌ El canal configurado no existe.", ephemeral=True)
            return
        try:
            embed = self.crear_embed(
                config["title"], config["description"], interaction.guild, interaction.user,
                config.get("image_url"), config.get("thumbnail_url"), is_leave=True,
            )
            await canal.send(embed=embed)
            resp = discord.Embed(description=f"✅ Mensaje de prueba enviado a {canal.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=resp, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sin permisos para enviar en ese canal.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcomes(bot))
