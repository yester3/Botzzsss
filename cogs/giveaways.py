"""
Sistema de giveaways:
- /giveaway: abre un modal para configurar el giveaway
- Botón para participar con custom_id único por giveaway
- Selección automática de ganadores
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import time
import random
import string
import re

import storage


def generate_giveaway_id():
    return f"{int(time.time())}_{(''.join(random.choices(string.ascii_lowercase, k=6)))}"


def parse_duration_to_seconds(duration_str: str):
    match = re.fullmatch(r"(\d+)([dhms])", duration_str.lower())
    if not match:
        return None
    cantidad, unidad = match.groups()
    cantidad = int(cantidad)
    conversiones = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return cantidad * conversiones.get(unidad, 0)


class GiveawayModal(discord.ui.Modal, title="Crear Giveaway"):
    titulo = discord.ui.TextInput(
        label="Nombre del premio",
        placeholder="MacBook Pro 16 pulgadas",
        max_length=100,
        required=True,
    )
    descripcion = discord.ui.TextInput(
        label="Descripción del giveaway",
        style=discord.TextStyle.paragraph,
        placeholder="Descripción del premio, instrucciones, etc.",
        max_length=1000,
        required=True,
    )
    duracion = discord.ui.TextInput(
        label="Duración (ej: 1d, 12h, 30m)",
        placeholder="1d",
        max_length=10,
        required=True,
    )
    ganadores = discord.ui.TextInput(
        label="Cantidad de ganadores",
        placeholder="3",
        max_length=2,
        required=True,
    )

    def __init__(self, canal: discord.TextChannel):
        super().__init__()
        self.canal = canal

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cantidad_ganadores = int(str(self.ganadores))
            if cantidad_ganadores < 1:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Cantidad de ganadores debe ser un número positivo", ephemeral=True
            )
            return

        duracion_str = str(self.duracion).lower().strip()
        duracion_segundos = parse_duration_to_seconds(duracion_str)
        if duracion_segundos is None:
            await interaction.response.send_message(
                "❌ Formato de duración inválido (usa: 1d, 12h, 30m, 20s)", ephemeral=True
            )
            return

        giveaway_id = generate_giveaway_id()
        end_time = time.time() + duracion_segundos

        giveaway_data = {
            "title": str(self.titulo),
            "description": str(self.descripcion),
            "creator_id": interaction.user.id,
            "created_at": time.time(),
            "end_time": end_time,
            "duration_seconds": duracion_segundos,
            "winners_count": cantidad_ganadores,
            "participants": [],
            "winners": [],
            "ended": False,
            "channel_id": self.canal.id,
            "message_id": None,
        }

        storage.create_giveaway(interaction.guild.id, giveaway_id, giveaway_data)

        embed = discord.Embed(
            title=f"🎁 GIVEAWAY: {str(self.titulo)}",
            description=str(self.descripcion),
            color=discord.Color.gold(),
        )
        embed.add_field(name="⏰ Finaliza en", value=f"<t:{int(end_time)}:R>", inline=False)
        embed.add_field(name="🏆 Ganadores", value=f"{cantidad_ganadores}", inline=True)
        embed.add_field(name="👥 Participantes", value="0", inline=True)
        embed.set_footer(text=f"ID: {giveaway_id}")

        # Cada giveaway tiene su propio custom_id único — evita conflictos entre giveaways
        msg = await self.canal.send(
            embed=embed,
            view=GiveawayJoinView(interaction.guild.id, giveaway_id),
        )

        giveaway_data["message_id"] = msg.id
        storage.create_giveaway(interaction.guild.id, giveaway_id, giveaway_data)

        confirm_embed = discord.Embed(
            title="✅ Giveaway Creado",
            description=f"El giveaway fue enviado a {self.canal.mention}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)


class GiveawayJoinView(discord.ui.View):
    """
    Vista con un botón cuyo custom_id incluye el giveaway_id.
    Esto evita que múltiples giveaways activos se mezclen entre sí.
    """

    def __init__(self, guild_id: int, giveaway_id: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.giveaway_id = giveaway_id

        btn = discord.ui.Button(
            label="Participar",
            emoji="🎁",
            style=discord.ButtonStyle.gold,
            custom_id=f"giveaway_join_{giveaway_id}",
        )
        btn.callback = self._join_callback
        self.add_item(btn)

    async def _join_callback(self, interaction: discord.Interaction):
        giveaway = storage.get_giveaway(self.guild_id, self.giveaway_id)

        if not giveaway:
            await interaction.response.send_message("❌ Este giveaway ya no existe", ephemeral=True)
            return

        if giveaway["ended"]:
            await interaction.response.send_message("❌ Este giveaway ya terminó", ephemeral=True)
            return

        if interaction.user.id in giveaway["participants"]:
            await interaction.response.send_message(
                "⚠️ Ya estás participando en este giveaway", ephemeral=True
            )
            return

        success = storage.add_giveaway_participant(self.guild_id, self.giveaway_id, interaction.user.id)

        if success:
            embed = discord.Embed(
                description="✅ ¡Ahora estás participando en el giveaway!",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            try:
                giveaway_updated = storage.get_giveaway(self.guild_id, self.giveaway_id)
                guild = interaction.client.get_guild(self.guild_id)
                channel = guild.get_channel(giveaway_updated["channel_id"])
                message = await channel.fetch_message(giveaway_updated["message_id"])

                embed_updated = discord.Embed(
                    title=f"🎁 GIVEAWAY: {giveaway_updated['title']}",
                    description=giveaway_updated["description"],
                    color=discord.Color.gold(),
                )
                embed_updated.add_field(
                    name="⏰ Finaliza en", value=f"<t:{int(giveaway_updated['end_time'])}:R>", inline=False
                )
                embed_updated.add_field(
                    name="🏆 Ganadores", value=f"{giveaway_updated['winners_count']}", inline=True
                )
                embed_updated.add_field(
                    name="👥 Participantes", value=f"{len(giveaway_updated['participants'])}", inline=True
                )
                embed_updated.set_footer(text=f"ID: {self.giveaway_id}")
                await message.edit(embed=embed_updated)
            except Exception as e:
                print(f"Error actualizando giveaway: {e}")
        else:
            await interaction.response.send_message("❌ Error al participar", ephemeral=True)


class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.giveaway_checker.start()

    def cog_unload(self):
        self.giveaway_checker.cancel()

    @tasks.loop(minutes=1)
    async def giveaway_checker(self):
        current_time = time.time()
        for guild in self.bot.guilds:
            giveaways = storage.get_all_giveaways(guild.id)
            for giveaway_id, giveaway in giveaways.items():
                if giveaway["ended"]:
                    continue
                if current_time >= giveaway["end_time"]:
                    await self.end_giveaway(guild, giveaway_id, giveaway)

    @giveaway_checker.before_loop
    async def before_giveaway_checker(self):
        await self.bot.wait_until_ready()
        # Re-registrar vistas de giveaways activos para que los botones
        # funcionen correctamente tras reiniciar el bot
        for guild in self.bot.guilds:
            giveaways = storage.get_all_giveaways(guild.id)
            for giveaway_id, giveaway in giveaways.items():
                if not giveaway.get("ended", False):
                    self.bot.add_view(
                        GiveawayJoinView(guild.id, giveaway_id),
                        message_id=giveaway.get("message_id"),
                    )

    async def end_giveaway(self, guild: discord.Guild, giveaway_id: str, giveaway: dict):
        participants = giveaway.get("participants", [])
        winners_count = giveaway.get("winners_count", 1)

        winners = random.sample(participants, min(len(participants), winners_count))

        giveaway["ended"] = True
        giveaway["winners"] = winners
        storage.create_giveaway(guild.id, giveaway_id, giveaway)

        channel = guild.get_channel(giveaway["channel_id"])
        if not channel:
            return

        winners_mentions = ", ".join([f"<@{w}>" for w in winners]) if winners else "Nadie participó 😢"

        embed = discord.Embed(
            title=f"🎉 GIVEAWAY TERMINADO: {giveaway['title']}",
            description=giveaway["description"],
            color=discord.Color.gold(),
        )
        embed.add_field(name="🏆 Ganador(es)", value=winners_mentions, inline=False)
        embed.add_field(name="👥 Total de Participantes", value=len(participants), inline=False)
        embed.set_footer(text=f"Giveaway finalizado | ID: {giveaway_id}")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @app_commands.command(name="giveaway", description="Crea un giveaway")
    @app_commands.describe(canal="Canal donde se enviará el giveaway (default: canal actual)")
    @app_commands.checks.has_permissions(administrator=True)
    async def giveaway(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        destino = canal or interaction.channel
        await interaction.response.send_modal(GiveawayModal(destino))

    @app_commands.command(name="giveaways", description="📊 Ver los giveaways activos del servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_giveaways_slash(self, interaction: discord.Interaction):
        giveaways = storage.get_all_giveaways(interaction.guild.id)
        active = [g for g in giveaways.values() if not g["ended"]]
        if not active:
            embed = discord.Embed(description="No hay giveaways activos", color=discord.Color.greyple())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(title="🎁 Giveaways Activos", color=discord.Color.gold())
        for g in active[:10]:
            embed.add_field(name=g["title"],
                            value=f"**Participantes:** {len(g['participants'])}\n"
                                  f"**Ganadores:** {g['winners_count']}\n"
                                  f"**Finaliza:** <t:{int(g['end_time'])}:R>",
                            inline=False)
        await interaction.response.send_message(embed=embed)

    @commands.command(name="giveaways", help="📊 Ver giveaways activos")
    @commands.has_permissions(administrator=True)
    async def list_giveaways(self, ctx: commands.Context):
        giveaways = storage.get_all_giveaways(ctx.guild.id)
        active = [g for g in giveaways.values() if not g["ended"]]

        if not active:
            embed = discord.Embed(description="No hay giveaways activos", color=discord.Color.greyple())
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title="🎁 Giveaways Activos", color=discord.Color.gold())
        for giveaway in active[:10]:
            embed.add_field(
                name=giveaway["title"],
                value=f"**Participantes:** {len(giveaway['participants'])}\n"
                      f"**Ganadores:** {giveaway['winners_count']}\n"
                      f"**Finaliza:** <t:{int(giveaway['end_time'])}:R>",
                inline=False,
            )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
