"""
Sistema de tickets profesional:
- /panelsetup: crea un panel customizable con modal
- Botones persistentes para crear, reclamar, cerrar tickets
- Notificaciones al rol de Staff cuando se abre un ticket
- Temporizador automático: cierra tickets inactivos tras 48h
- Mejor estética y manejo de errores
"""

import asyncio
import discord
import time
from discord import app_commands
from discord.ext import commands, tasks

import storage


def is_admin_interaction(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator


def get_admin_and_staff_roles(guild: discord.Guild, user: discord.User = None):
    """Retorna list de roles admin + staff_role si existe."""
    roles = [role for role in guild.roles if role.permissions.administrator]
    staff_role_id = storage.get_staff_role(guild.id)
    if staff_role_id:
        staff_role = guild.get_role(staff_role_id)
        if staff_role and staff_role not in roles:
            roles.append(staff_role)
    return roles


# ---------------------------------------------------------------
# MODAL: pedir título y descripción del panel
# ---------------------------------------------------------------
class PanelModal(discord.ui.Modal, title="Configurar Panel de Tickets"):

    titulo = discord.ui.TextInput(
        label="Título del panel",
        placeholder="📩 Centro de Soporte",
        max_length=100,
        required=True,
    )
    descripcion = discord.ui.TextInput(
        label="Descripción del panel",
        style=discord.TextStyle.paragraph,
        placeholder="Haz clic en el botón para abrir un ticket con nuestro equipo de soporte.",
        max_length=1000,
        required=True,
    )

    def __init__(self, canal_destino: discord.TextChannel, categoria: discord.CategoryChannel | None):
        super().__init__()
        self.canal_destino = canal_destino
        self.categoria = categoria

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=str(self.titulo),
            description=str(self.descripcion),
            color=discord.Color.blurple(),
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"{interaction.guild.name} | Haz clic en el botón de abajo")

        await self.canal_destino.send(embed=embed, view=TicketPanelView())

        if self.categoria:
            storage.set_ticket_category(interaction.guild.id, self.categoria.id)

        status_msg = f"✅ Panel enviado en {self.canal_destino.mention}"
        if self.categoria:
            status_msg += f"\n📁 Categoría: **{self.categoria.name}**"
        else:
            status_msg += "\n⚠️ No se configuró categoría. Los tickets se crearán en la raíz."

        embed_confirm = discord.Embed(
            title="✅ Panel Creado",
            description=status_msg,
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed_confirm, ephemeral=True)


# ---------------------------------------------------------------
# VISTA: panel público con botón "Crear Ticket"
# ---------------------------------------------------------------
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Crear Ticket", emoji="🎫", style=discord.ButtonStyle.green, custom_id="ticket_create_button")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild

        # ¿Ya tiene un ticket abierto?
        existing_channel_id = storage.get_open_ticket_channel_for_user(guild.id, interaction.user.id)
        if existing_channel_id:
            canal_existente = guild.get_channel(existing_channel_id)
            if canal_existente:
                embed = discord.Embed(
                    description=f"⚠️ Ya tienes un ticket abierto: {canal_existente.mention}",
                    color=discord.Color.gold(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # Obtener categoría (validar que sea una categoría real)
        categoria = None
        cat_id = storage.get_ticket_category(guild.id)
        if cat_id:
            canal_categoria = guild.get_channel(cat_id)
            # Verificar que es una categoría y no otro tipo de canal
            if isinstance(canal_categoria, discord.CategoryChannel):
                categoria = canal_categoria
            else:
                # Si no es una categoría válida, limpiar el ID guardado
                storage.set_ticket_category(guild.id, None)

        # Construir overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
                manage_messages=True,
            ),
        }

        # Agregar roles de admin y staff
        for role in get_admin_and_staff_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
            )

        nombre_canal = f"ticket-{interaction.user.name}".lower().replace(" ", "-")[:90]

        try:
            # Crear el canal (con categoría si existe y es válida)
            if categoria:
                canal = await guild.create_text_channel(
                    name=nombre_canal,
                    category=categoria,
                    overwrites=overwrites,
                    topic=f"Ticket de {interaction.user.id} ({interaction.user.name})",
                    reason=f"Ticket creado por {interaction.user}",
                )
            else:
                # Sin categoría si no hay una configurada
                canal = await guild.create_text_channel(
                    name=nombre_canal,
                    overwrites=overwrites,
                    topic=f"Ticket de {interaction.user.id} ({interaction.user.name})",
                    reason=f"Ticket creado por {interaction.user}",
                )
        except discord.Forbidden as e:
            embed = discord.Embed(
                title="❌ Error de Permisos",
                description=f"No tengo permisos para crear canales.\n\n"
                           f"**Revisa que:**\n"
                           f"• Mi rol esté **por encima** de otros en Roles\n"
                           f"• Tenga permiso `Manage Channels`\n"
                           f"• La categoría no tenga 50+ canales\n"
                           f"• El servidor no esté limitado",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"[TICKET ERROR] Forbidden: {e}")
            return
        except discord.HTTPException as e:
            if "parent_id" in str(e):
                # Error de categoría inválida
                embed = discord.Embed(
                    title="❌ Error de Categoría",
                    description=f"La categoría configurada ya no existe o no es válida.\n\n"
                               f"**Solución:** ejecuta `/panelsetup` de nuevo y selecciona una categoría válida.",
                    color=discord.Color.red(),
                )
                storage.set_ticket_category(interaction.guild.id, None)
            else:
                embed = discord.Embed(
                    title="❌ Error al Crear Canal",
                    description=f"Discord rechazó la creación.\n\nError: `{str(e)}`",
                    color=discord.Color.red(),
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"[TICKET ERROR] HTTPException: {e}")
            return
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Inesperado",
                description=f"Algo salió mal.\n\nError: `{str(e)}`",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"[TICKET ERROR] Unexpected: {e}")
            return

        # Guardar ticket abierto
        storage.add_open_ticket(guild.id, interaction.user.id, canal.id)

        # Mensaje de bienvenida
        embed_welcome = discord.Embed(
            title="🎫 Ticket Abierto",
            description=(
                f"Hola {interaction.user.mention}, gracias por contactarnos.\n\n"
                f"Un miembro del equipo de soporte te atenderá pronto. Describe tu problema en los mensajes de abajo.\n\n"
                f"Usa el botón **Cerrar Ticket** cuando tu problema esté resuelto."
            ),
            color=discord.Color.green(),
        )
        embed_welcome.set_footer(text=f"Creado en {discord.utils.utcnow().strftime('%H:%M UTC')}")

        await canal.send(content=interaction.user.mention, embed=embed_welcome, view=TicketControlView())

        # Notificación a role de staff
        notify_role_id = storage.get_guild_data(guild.id).get("ticket_notify_role")
        if notify_role_id:
            notify_role = guild.get_role(notify_role_id)
            if notify_role:
                embed_notify = discord.Embed(
                    title="🔔 Nuevo Ticket",
                    description=f"{interaction.user.mention} ha abierto un ticket.\n{canal.mention}",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow(),
                )
                try:
                    # content= es necesario para que Discord envíe la notificación real al rol
                    await canal.send(content=notify_role.mention, embed=embed_notify)
                except Exception:
                    pass

        # Respuesta al usuario
        embed_response = discord.Embed(
            title="✅ Ticket Creado",
            description=f"Tu ticket fue creado: {canal.mention}",
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed_response, ephemeral=True)


# ---------------------------------------------------------------
# VISTA: confirmación de cierre
# ---------------------------------------------------------------
class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Sí, cerrar", style=discord.ButtonStyle.danger, custom_id="ticket_confirm_close")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔒 Cerrando Ticket",
            description="El canal se eliminará en 5 segundos...",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

        storage.remove_open_ticket_by_channel(interaction.guild.id, interaction.channel.id)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user}")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, custom_id="ticket_cancel_close")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description="❎ Cierre cancelado.",
            color=discord.Color.greyple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------
# VISTA: botones dentro del canal de ticket
# ---------------------------------------------------------------
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cerrar Ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="ticket_close_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚠️ ¿Cerrar Ticket?",
            description="¿Estás seguro? Esta acción es irreversible.",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView(), ephemeral=True)

    @discord.ui.button(label="Reclamar", emoji="🙋", style=discord.ButtonStyle.blurple, custom_id="ticket_claim_button")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = (
            interaction.user.guild_permissions.administrator or
            (storage.get_staff_role(interaction.guild.id) and 
             storage.get_staff_role(interaction.guild.id) in [r.id for r in interaction.user.roles])
        )
        
        if not is_staff:
            embed = discord.Embed(
                description="❌ Solo el staff puede reclamar tickets.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🙋 Ticket Reclamado",
            description=f"{interaction.user.mention} se encargará de tu caso.",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------
# COG
# ---------------------------------------------------------------
class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.inactivity_checker.start()

    def cog_unload(self):
        self.inactivity_checker.cancel()

    @tasks.loop(minutes=5)
    async def inactivity_checker(self):
        """Cada 5 minutos revisa tickets inactivos y los avisa/cierra."""
        for guild in self.bot.guilds:
            open_tickets = storage.get_open_tickets(guild.id)
            timeout_seconds = storage.get_inactivity_timeout(guild.id)
            current_time = time.time()

            for user_id_str, ticket_data in list(open_tickets.items()):
                if isinstance(ticket_data, dict):
                    channel_id = ticket_data.get("channel_id")
                    opened_at = ticket_data.get("opened_at", current_time)
                else:
                    # Compatibilidad con formato antiguo
                    channel_id = ticket_data
                    opened_at = current_time

                channel = guild.get_channel(channel_id)
                if not channel:
                    storage.remove_open_ticket_by_channel(guild.id, channel_id)
                    continue

                # Revisar inactividad por el último mensaje del canal
                try:
                    last_msg = None
                    async for msg in channel.history(limit=1):
                        last_msg = msg
                    if last_msg is None:
                        # Canal vacío — usar tiempo de apertura del ticket
                        last_ts = opened_at
                    else:
                        last_ts = last_msg.created_at.timestamp()

                    inactivity = current_time - last_ts

                    # Primera advertencia: a mitad del timeout
                    if timeout_seconds / 2 < inactivity < timeout_seconds:
                        # Solo avisar si el último mensaje NO es ya un aviso del bot
                        if last_msg and last_msg.author.id != self.bot.user.id:
                            embed_warn = discord.Embed(
                                title="⏰ Ticket sin actividad",
                                description="Este ticket lleva tiempo sin mensajes.\n"
                                            "Se cerrará automáticamente si no hay actividad.",
                                color=discord.Color.gold(),
                            )
                            try:
                                await channel.send(embed=embed_warn)
                            except Exception:
                                pass

                    # Cierre automático: pasado el timeout completo
                    elif inactivity >= timeout_seconds:
                        embed_close = discord.Embed(
                            title="🔒 Ticket Cerrado por Inactividad",
                            description=f"Este ticket fue cerrado automáticamente tras "
                                        f"{int(timeout_seconds / 3600)}h sin actividad.",
                            color=discord.Color.red(),
                        )
                        try:
                            await channel.send(embed=embed_close)
                        except Exception:
                            pass
                        await asyncio.sleep(5)
                        storage.remove_open_ticket_by_channel(guild.id, channel.id)
                        try:
                            await channel.delete(reason="Cierre automático por inactividad")
                        except (discord.Forbidden, discord.NotFound):
                            pass
                except discord.Forbidden:
                    pass

    @inactivity_checker.before_loop
    async def before_inactivity_checker(self):
        await self.bot.wait_until_ready()

    async def autocomplete_categorias(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        """Autocomplete que solo muestra categorías."""
        if not interaction.guild:
            return []
        categorias = [c for c in interaction.guild.categories]
        return [
            app_commands.Choice(name=cat.name, value=str(cat.id))
            for cat in categorias
            if current.lower() in cat.name.lower()
        ][:25]

    @app_commands.command(name="panelsetup", description="Crea un panel de tickets (Solo Administradores)")
    @app_commands.describe(
        canal="Canal donde se envía el panel",
        categoria="Categoría donde irán los tickets",
    )
    @app_commands.autocomplete(categoria=autocomplete_categorias)
    async def panelsetup(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel = None,
        categoria: str = None,
    ):
        if not is_admin_interaction(interaction):
            embed = discord.Embed(
                description="❌ Necesitas permisos de **Administrador** para usar este comando.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        destino = canal or interaction.channel
        
        # Convertir categoria string ID a objeto CategoryChannel
        categoria_obj = None
        if categoria:
            try:
                cat_id = int(categoria)
                categoria_obj = interaction.guild.get_channel(cat_id)
                if not isinstance(categoria_obj, discord.CategoryChannel):
                    await interaction.response.send_message(
                        "❌ El ID no corresponde a una categoría válida.",
                        ephemeral=True
                    )
                    return
            except (ValueError, TypeError):
                pass
        
        await interaction.response.send_modal(PanelModal(destino, categoria_obj))


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
