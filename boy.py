import discord
from discord.ext import commands
import asyncio
import os
from flask import Flask
from threading import Thread

# -------------------------------------------------------------
# CONFIGURACIÓN DEL SERVIDOR WEB (PARA RENDER + UPTIMEROBOT)
# -------------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "¡Zeef Store Bot está activo 24/7!"

def run_web():
    # Render asigna un puerto automáticamente a través de la variable de entorno PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# -------------------------------------------------------------
# CONFIGURACIÓN Y VARIABLES GLOBALES DE DISCORD
# -------------------------------------------------------------
TICKET_COUNTER = 0
CATEGORY_ID = None  # ID de la categoría de tickets (Opcional)
STAFF_ROLE_ID = 1564836416662409266  # ID del Rol Staff de Zeef Store
CLIENT_ROLE_ID = None  # ID del rol de cliente automático tras entregar (Opcional)

# Tus datos reales de Naranja X
ALIAS_NARANJA_X = "17.NICOLASS"
CBU_NARANJA_X = "4530000800013509630025"
TITULAR_NARANJA_X = "LUCAS NICOLAS BERTI MANSILLA"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------------------------------------------
# MODAL PARA APROBAR Y ENTREGAR EL PRODUCTO (SOLO STAFF)
# -------------------------------------------------------------
class DeliveryModal(discord.ui.Modal, title="🎁 Entrega de Producto"):
    producto_clave = discord.ui.TextInput(
        label="Licencia / Archivo / Instrucciones",
        placeholder="Pega aquí la clave de activación, link o credenciales...",
        style=discord.TextStyle.paragraph,
        required=True
    )

    def __init__(self, target_user: discord.User):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Enviar el producto por Mensaje Directo (MD) al comprador
        try:
            await self.target_user.send(
                f"🎉 **¡Tu pago en Zeef Store ha sido verificado con éxito!**\n\n"
                f"📦 **Detalles de tu entrega:**\n"
                f"```{self.producto_clave.value}```\n\n"
                f"Gracias por confiar en **Zeef Store**. Ante cualquier consulta, estamos a tu disposición."
            )
            md_sent = True
        except discord.Forbidden:
            md_sent = False

        # 2. Intentar asignarle el rol de cliente en el servidor
        guild = interaction.guild
        member = guild.get_member(self.target_user.id)
        if member and CLIENT_ROLE_ID:
            role = guild.get_role(CLIENT_ROLE_ID)
            if role:
                try:
                    await member.add_roles(role)
                except Exception:
                    pass

        # 3. Notificar en el canal y programar el cierre del ticket
        if md_sent:
            await interaction.response.send_message(
                f"✅ **¡Entrega completada con éxito!** El producto fue enviado por MD a {self.target_user.mention}.\n"
                f"🔒 Este canal se eliminará automáticamente en 10 segundos..."
            )
        else:
            await interaction.response.send_message(
                f"⚠️ El usuario tiene los DMs cerrados. Se le adjunta la entrega aquí mismo:\n"
                f"```{self.producto_clave.value}```\n"
                f"🔒 Este canal se eliminará automáticamente en 30 segundos..."
            )

        # Esperar y borrar el canal de ticket
        await asyncio.sleep(10 if md_sent else 30)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

# -------------------------------------------------------------
# BOTÓN DE CONTROL PARA EL STAFF EN EL TICKET DE COMPRA
# -------------------------------------------------------------
class StaffControlView(discord.ui.View):
    def __init__(self, buyer_user: discord.User):
        super().__init__(timeout=None)
        self.buyer_user = buyer_user

    @discord.ui.button(label="Aprobar y Entregar", style=discord.ButtonStyle.green, emoji="✅", custom_id="btn_approve_delivery")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        is_staff = (staff_role in interaction.user.roles) if staff_role else interaction.user.guild_permissions.administrator

        if not is_staff:
            await interaction.response.send_message("❌ Solo el equipo de Staff puede aprobar pagos y entregar productos.", ephemeral=True)
            return

        await interaction.response.send_modal(DeliveryModal(target_user=self.buyer_user))

# -------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA CREAR EL CANAL DE TICKET
# -------------------------------------------------------------
async def create_ticket_channel(interaction: discord.Interaction, ticket_type: str, details_text: str):
    global TICKET_COUNTER
    guild = interaction.guild
    user = interaction.user

    await interaction.response.send_message(
        "🔄 Procesando tu solicitud y creando tu canal de ticket...",
        ephemeral=True
    )

    TICKET_COUNTER += 1
    channel_name = f"ticket-{user.name.lower()}-{TICKET_COUNTER}"

    staff_role = guild.get_role(STAFF_ROLE_ID)
    
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    category = guild.get_channel(CATEGORY_ID) if CATEGORY_ID else None

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        reason=f"Ticket #{TICKET_COUNTER} abierto por {user.name}"
    )

    # 1. Enviar mensaje por MD al usuario
    try:
        await user.send(f"Hola {user.mention} gracias por abrir ticket en Zeef Store en breve un staff te respondera")
    except discord.Forbidden:
        pass

    # 2. Agregar instrucciones de Naranja X si es ticket de Compra
    payment_info = ""
    if ticket_type == "Compra":
        payment_info = (
            f"\n\n💳 **Datos para realizar tu pago por Naranja X:**\n"
            f"• **Alias:** `{ALIAS_NARANJA_X}`\n"
            f"• **CBU:** `{CBU_NARANJA_X}`\n"
            f"• **Titular:** `{TITULAR_NARANJA_X}`\n\n"
            f"📌 **Instrucciones:** Realiza la transferencia por Naranja X y **sube aquí la captura del comprobante**. "
            f"En cuanto un Staff verifique el dinero, presionará el botón verde de entrega."
        )

    embed_welcome = discord.Embed(
        title=f"🎫 Ticket #{TICKET_COUNTER} — {ticket_type}",
        description=(
            f"Hola {user.mention} como estas espero que bien en Zeef Queremos lo mejor "
            f"para ustedes como para nosotros te pido porfavor que esperes en breve un staff "
            f"se contactara contigo para ayuarte en lo que necesitas.\n\n"
            f"**Información recopilada:**\n{details_text}"
            f"{payment_info}"
        ),
        color=discord.Color.from_str("#00c3ff")
    )
    embed_welcome.set_footer(text="Zeef Store • Sistema de Soporte")

    staff_mention = f"<@&{STAFF_ROLE_ID}>" if staff_role else "@Staff"
    ping_text = f"Hola staff {staff_mention} {user.mention} un usuario abrio ticket responde para que no espere"

    view_to_send = StaffControlView(buyer_user=user) if ticket_type == "Compra" else None

    await ticket_channel.send(content=ping_text, embed=embed_welcome, view=view_to_send)

    await interaction.edit_original_response(
        content=f"✅ ¡Tu ticket ha sido creado exitosamente! Dirígete a {ticket_channel.mention}"
    )

# -------------------------------------------------------------
# MODALES PARA CADA OPCIÓN DEL PANEL
# -------------------------------------------------------------
class SupportModal(discord.ui.Modal, title="🛠️ Soporte Técnico | Support"):
    asunto = discord.ui.TextInput(label="Asunto / Issue", placeholder="Ej: Problema al ejecutar", required=True)
    descripcion = discord.ui.TextInput(label="Detalles del problema", placeholder="Explica lo que te sucede...", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        details = f"📌 **Asunto:** {self.asunto.value}\n💬 **Descripción:** {self.descripcion.value}"
        await create_ticket_channel(interaction, "Soporte", details)

class DudasModal(discord.ui.Modal, title="❓ Consulta General | Doubts"):
    pregunta = discord.ui.TextInput(label="¿Cuál es tu duda?", placeholder="Escribe tu consulta aquí...", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        details = f"❓ **Consulta:** {self.pregunta.value}"
        await create_ticket_channel(interaction, "Dudas", details)

class BuyModal(discord.ui.Modal, title="🛒 Formulario de Compra | Buy"):
    producto = discord.ui.TextInput(label="Producto que deseas adquirir", placeholder="Ej: saytus external", required=True)
    metodo_pago = discord.ui.TextInput(label="Método de pago", placeholder="Ej: Naranja X", required=True)
    notas = discord.ui.TextInput(label="Notas adicionales (Opcional)", placeholder="Ej: ID del producto.", style=discord.TextStyle.paragraph, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        details = (
            f"📦 **Producto:** {self.producto.value}\n"
            f"💳 **Método de Pago:** {self.metodo_pago.value}\n"
            f"📝 **Notas:** {self.notas.value if self.notas.value else 'Ninguna'}"
        )
        await create_ticket_channel(interaction, "Compra", details)

# -------------------------------------------------------------
# BOTONES DEL PANEL PRINCIPAL
# -------------------------------------------------------------
class TicketButtonsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Support | Soporte", style=discord.ButtonStyle.blurple, emoji="🎧", custom_id="btn_support")
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SupportModal())

    @discord.ui.button(label="Dudas | Questions", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="btn_dudas")
    async def dudas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DudasModal())

    @discord.ui.button(label="Buy | Comprar", style=discord.ButtonStyle.primary, emoji="🛒", custom_id="btn_buy")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BuyModal())

# -------------------------------------------------------------
# EVENTOS Y COMANDOS
# -------------------------------------------------------------
@bot.event
async def on_ready():
    bot.add_view(TicketButtonsView())
    print(f"Bot conectado como: {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.message.delete()

    embed = discord.Embed(
        title="SZ  Zeef | Sistema de Soporte",
        description=(
            "🇪🇸 **Elige una de las siguientes opciones para continuar según lo que necesites.**\n\n"
            "🇺🇸 **Choose one of the options below to proceed based on what you need.**\n\n"
            "🛠️ **Support** — Soporte técnico y asistencia · Technical help & support\n"
            "❓ **Dudas** — Consultas generales y preguntas · General questions\n"
            "🛒 **Buy** — Adquiere un producto o servicio · Purchase a product\n\n"
            "> ⏰ *Nuestro equipo te responderá lo antes posible · Our team will reply as soon as possible.*"
        ),
        color=discord.Color.from_str("#00c3ff")
    )

    embed.set_image(url="https://i.ibb.co/banner-ticket.png")
    embed.set_footer(text="© 2026 Zeef Store. Todos los derechos reservados")

    await ctx.send(embed=embed, view=TicketButtonsView())

if __name__ == "__main__":
    # Arrancar el servidor web en segundo plano para Render
    keep_alive()
    # Arrancar el bot de Discord
    bot.run("MTUwNDYzMDI4OTUzNDgxMjIxMA.GJHf6F.Ciu5gQn8I1ab8E8kUK1K1Mo3NgJV6vJZd9yj4s")