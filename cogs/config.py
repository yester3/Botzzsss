"""
Cog de configuración del bot:
- /setrole: asigna un rol que puede usar comandos de moderación
- /setlog: configura un canal específico para un tipo de log
- /setalllog: configura un solo canal para TODOS los logs
- /clearlogs: limpia todos los canales de logs configurados
- /ticketnotify: configura el rol que recibe notificación de nuevos tickets
- /keepalive: configura el canal de keep-alive (para mantener bot activo)
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio

import storage


class Config(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.keep_alive_task.start()

    def cog_unload(self):
        self.keep_alive_task.cancel()

    @tasks.loop(minutes=10)
    async def keep_alive_task(self):
        """Cada 10 minutos envía un mensaje de keep-alive en el canal configurado."""
        for guild in self.bot.guilds:
            channel_id = storage.get_guild_data(guild.id).get("keep_alive_channel")
            if not channel_id:
                continue

            channel = guild.get_channel(channel_id)
            if not channel:
                continue

            try:
                # Enviar mensaje invisible (solo para mantener tráfico)
                msg = await channel.send("⏰ Keep-alive ping")
                # Eliminar después de 1 segundo
                await asyncio.sleep(1)
                await msg.delete()
            except discord.Forbidden:
                pass  # Sin permisos
            except discord.NotFound:
                pass  # Mensaje ya fue borrado
            except Exception:
                pass  # Otro error, ignorar

    @keep_alive_task.before_loop
    async def before_keep_alive(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="keepalive", description="Configura el canal de keep-alive (mantiene el bot activo)")
    @app_commands.describe(
        canal="El canal donde se enviarán los pings de keep-alive (o déjalo vacío para desactivar)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def keepalive(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        """Configura keep-alive para que el bot nunca se duerma."""
        if canal:
            storage.update_guild_data(interaction.guild.id, keep_alive_channel=canal.id)
            
            embed = discord.Embed(
                title="✅ Keep-Alive Activado",
                description=f"El bot enviará pings de keep-alive cada 10 minutos en {canal.mention}\n\n"
                           f"Los mensajes se eliminarán automáticamente después de 1 segundo.\n"
                           f"**Esto mantiene el bot activo 24/7 en Replit.**",
                color=discord.Color.green(),
            )
            embed.set_footer(text="Ideal para mantener Replit sin dormirse")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            storage.update_guild_data(interaction.guild.id, keep_alive_channel=None)
            
            embed = discord.Embed(
                title="❌ Keep-Alive Desactivado",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setrole", description="Asigna un rol que puede usar comandos de moderación")
    @app_commands.describe(rol="El rol que tendrá acceso a comandos de mod")
    @app_commands.checks.has_permissions(administrator=True)
    async def setrole(self, interaction: discord.Interaction, rol: discord.Role):
        """Solo Administradores pueden configurar esto."""
        storage.set_staff_role(interaction.guild.id, rol.id)
        
        embed = discord.Embed(
            title="✅ Rol de Staff Configurado",
            description=f"El rol {rol.mention} ahora puede usar todos los comandos de moderación.",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Configurado por {interaction.user.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setlog", description="Configura un canal para un tipo específico de log")
    @app_commands.describe(
        tipo="Tipo de log (kicks, bans, warns, mutes, locks, tickets)",
        canal="El canal donde se enviarán los logs de ese tipo",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setlog(self, interaction: discord.Interaction, tipo: str, canal: discord.TextChannel):
        """Configura un canal de logs para un tipo específico."""
        tipos_validos = ["kicks", "bans", "warns", "mutes", "locks", "tickets"]
        if tipo.lower() not in tipos_validos:
            await interaction.response.send_message(
                f"❌ Tipo de log inválido. Elige entre: {', '.join(tipos_validos)}",
                ephemeral=True,
            )
            return
        
        storage.set_log_channel(interaction.guild.id, tipo.lower(), canal.id)
        
        embed = discord.Embed(
            title="✅ Canal de Log Configurado",
            description=f"Logs de **{tipo.upper()}** se enviarán a {canal.mention}",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Configurado por {interaction.user.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setalllog", description="Configura un solo canal para TODOS los logs")
    @app_commands.describe(canal="El canal donde irán todos los logs")
    @app_commands.checks.has_permissions(administrator=True)
    async def setalllog(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Configura un canal único para todos los tipos de logs."""
        storage.set_log_channel(interaction.guild.id, "all", canal.id)
        
        embed = discord.Embed(
            title="✅ Canal de Logs General Configurado",
            description=f"**TODOS** los logs se enviarán a {canal.mention}\n"
                       f"(kicks, bans, warns, mutes, locks, tickets)",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Configurado por {interaction.user.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ticketnotify", description="Configura el rol que recibe notificaciones de nuevos tickets")
    @app_commands.describe(rol="El rol que será notificado (deja vacío para desactivar)")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketnotify(self, interaction: discord.Interaction, rol: discord.Role = None):
        """Configura quién recibe ping cuando se abre un ticket."""
        if rol:
            storage.update_guild_data(interaction.guild.id, ticket_notify_role=rol.id)
            embed = discord.Embed(
                title="✅ Notificaciones de Tickets Activadas",
                description=f"El rol {rol.mention} será notificado cuando se abra un ticket.",
                color=discord.Color.green(),
            )
        else:
            storage.update_guild_data(interaction.guild.id, ticket_notify_role=None)
            embed = discord.Embed(
                title="❌ Notificaciones de Tickets Desactivadas",
                color=discord.Color.red(),
            )
        
        embed.set_footer(text=f"Configurado por {interaction.user.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearlogs", description="Limpia la configuración de todos los canales de logs")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearlogs(self, interaction: discord.Interaction):
        storage.update_guild_data(interaction.guild.id, log_channels={})
        embed = discord.Embed(
            title="🧹 Logs Limpiados",
            description="Toda la configuración de canales de logs ha sido eliminada.",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ======== AUTOROLE ========

    @app_commands.command(name="autorole", description="Asigna un rol automáticamente a nuevos miembros")
    @app_commands.describe(rol="Rol a asignar (deja vacío para desactivar)")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole(self, interaction: discord.Interaction, rol: discord.Role = None):
        if rol:
            if rol >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    "❌ No puedo asignar ese rol — está por encima del mío en la jerarquía.",
                    ephemeral=True,
                )
                return
            storage.set_autorole(interaction.guild.id, rol.id)
            embed = discord.Embed(
                title="✅ Autorole Configurado",
                description=f"Todos los nuevos miembros recibirán el rol {rol.mention} automáticamente.",
                color=discord.Color.green(),
            )
        else:
            storage.set_autorole(interaction.guild.id, None)
            embed = discord.Embed(
                title="❌ Autorole Desactivado",
                description="Los nuevos miembros ya no recibirán ningún rol automático.",
                color=discord.Color.red(),
            )
        embed.set_footer(text=f"Configurado por {interaction.user.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ======== WEBHOOKS ========

    @app_commands.command(name="webhookcreate", description="Crea una webhook en un canal")
    @app_commands.describe(
        canal="Canal donde se creará la webhook",
        nombre="Nombre de la webhook",
    )
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def webhookcreate(self, interaction: discord.Interaction, canal: discord.TextChannel, nombre: str):
        if not canal.permissions_for(interaction.guild.me).manage_webhooks:
            await interaction.response.send_message(
                f"❌ No tengo permisos para gestionar webhooks en {canal.mention}.", ephemeral=True
            )
            return

        try:
            webhook = await canal.create_webhook(
                name=nombre,
                reason=f"Creada por {interaction.user} vía /webhookcreate",
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ No tengo permisos suficientes.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Error al crear la webhook: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔗 Webhook Creada",
            color=discord.Color.green(),
        )
        embed.add_field(name="📝 Nombre", value=nombre, inline=True)
        embed.add_field(name="📍 Canal", value=canal.mention, inline=True)
        embed.add_field(
            name="🔗 URL — copia esta línea completa",
            value=f"```\n{webhook.url}\n```",
            inline=False,
        )
        embed.set_footer(text="⚠️ Guarda esta URL — no podrás verla de nuevo")
        # ephemeral=True para que solo el que crea la webhook vea la URL
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="webhookdelete", description="Elimina una webhook por nombre")
    @app_commands.describe(nombre="Nombre exacto de la webhook a eliminar")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    async def webhookdelete(self, interaction: discord.Interaction, nombre: str):
        await interaction.response.defer(ephemeral=True)
        try:
            webhooks = await interaction.guild.webhooks()
        except discord.Forbidden:
            await interaction.followup.send("❌ No tengo permisos para ver las webhooks del servidor.")
            return

        coincidencias = [w for w in webhooks if w.name.lower() == nombre.lower()]
        if not coincidencias:
            nombres_existentes = ", ".join(f"`{w.name}`" for w in webhooks) or "ninguna"
            embed = discord.Embed(
                title="❌ Webhook No Encontrada",
                description=f"No hay ninguna webhook llamada **`{nombre}`**.\n\n**Webhooks existentes:** {nombres_existentes}",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        eliminadas = 0
        for w in coincidencias:
            try:
                await w.delete(reason=f"Eliminada por {interaction.user} vía /webhookdelete")
                eliminadas += 1
            except discord.Forbidden:
                pass

        if eliminadas:
            embed = discord.Embed(
                title="✅ Webhook Eliminada",
                description=f"Se eliminaron **{eliminadas}** webhook(s) llamada(s) `{nombre}`.",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="No se pudo eliminar la webhook (sin permisos).",
                color=discord.Color.red(),
            )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))
