import asyncio
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands


class WebhookSender(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="webhooksender",
        description="Envía mensajes a una webhook de Discord con nombre y avatar personalizados.",
    )
    @app_commands.describe(
        url="URL de la webhook de Discord",
        mensaje="Mensaje a enviar",
        cantidad="Número de veces que se enviará el mensaje (máx 1000)",
        delay="Segundos de espera entre cada envío (ej: 0.5)",
        username="Nombre que aparecerá como remitente (opcional)",
        avatar_url="URL de imagen para el avatar del remitente (opcional)",
    )
    async def webhooksender(
        self,
        interaction: discord.Interaction,
        url: str,
        mensaje: str,
        cantidad: app_commands.Range[int, 1, 1000] = 1,
        delay: float = 0.5,
        username: str = None,
        avatar_url: str = None,
    ):
        if not url.startswith("https://discord.com/api/webhooks/") and \
           not url.startswith("https://discordapp.com/api/webhooks/") and \
           not url.startswith("https://ptb.discord.com/api/webhooks/") and \
           not url.startswith("https://canary.discord.com/api/webhooks/"):
            await interaction.response.send_message(
                "❌ La URL no parece ser una webhook válida de Discord.",
                ephemeral=True,
            )
            return

        if avatar_url and not (avatar_url.startswith("http://") or avatar_url.startswith("https://")):
            await interaction.response.send_message(
                "❌ El `avatar_url` debe ser una URL válida que empiece con `http://` o `https://`.",
                ephemeral=True,
            )
            return

        if delay < 0:
            delay = 0

        desc_lines = [
            f"**Webhook:** `...{url[-30:]}`",
            f"**Mensaje:** {mensaje[:100]}{'...' if len(mensaje) > 100 else ''}",
            f"**Cantidad:** {cantidad}",
            f"**Delay:** {delay}s",
        ]
        if username:
            desc_lines.append(f"**Nombre:** {username}")
        if avatar_url:
            desc_lines.append(f"**Avatar:** [ver imagen]({avatar_url})")
        desc_lines.append("\nEl proceso corre en segundo plano.")

        await interaction.response.send_message(
            embed=discord.Embed(
                title="📤 Enviando mensajes...",
                description="\n".join(desc_lines),
                color=discord.Color.blurple(),
            ),
            ephemeral=True,
        )

        asyncio.ensure_future(
            self._enviar(interaction, url, mensaje, cantidad, delay, username, avatar_url)
        )

    async def _enviar(
        self,
        interaction: discord.Interaction,
        url: str,
        mensaje: str,
        cantidad: int,
        delay: float,
        username: str = None,
        avatar_url: str = None,
    ):
        enviados = 0
        errores = 0

        payload = {"content": mensaje}
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url

        async with aiohttp.ClientSession() as session:
            for _ in range(cantidad):
                try:
                    async with session.post(url, json=payload) as resp:
                        if resp.status in (200, 204):
                            enviados += 1
                        elif resp.status == 429:
                            data = await resp.json()
                            espera = float(data.get("retry_after", delay + 1))
                            await asyncio.sleep(espera)
                            async with session.post(url, json=payload) as retry:
                                if retry.status in (200, 204):
                                    enviados += 1
                                else:
                                    errores += 1
                        else:
                            errores += 1
                except Exception:
                    errores += 1

                if delay > 0:
                    await asyncio.sleep(delay)

        try:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Envío completado",
                    description=(
                        f"**Enviados:** {enviados}\n"
                        f"**Errores:** {errores}\n"
                        f"**Total intentos:** {cantidad}"
                    ),
                    color=discord.Color.green() if errores == 0 else discord.Color.orange(),
                ),
                ephemeral=True,
            )
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(WebhookSender(bot))
