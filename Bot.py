import os
import random
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- CONFIGURACIÓN ---
TOKEN = "9230845768:AAGyLDa9vUuC4nAC6nNfR1IUeV7JzTISChw"
ADMIN_ID = 8584917327

# --- BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect("bot_rajona.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            weight INTEGER DEFAULT 1,
            caption TEXT DEFAULT ''
        )
    """
    )
    conn.commit()
    conn.close()

init_db()

# --- COMANDO /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    if chat_type != "private":
        keyboard = [[InlineKeyboardButton("🎲 Rajona al azar", callback_data="rajona_azur")]]
        await update.message.reply_text(
            "¡Hola! Presiona el botón de abajo para recibir tu 'Rajona al azar' por mensaje privado (asegúrate de haberme hablado al privado antes).",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🎲 Rajona al azar", callback_data="rajona_azur")],
            [InlineKeyboardButton("⚙️ Panel de Administración", callback_data="admin_menu")],
        ]
        await update.message.reply_text(
            "¡Hola Admin! Elige una opción:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("🎲 Rajona al azar", callback_data="rajona_azur")]]
        await update.message.reply_text(
            "¡Hola! Presiona el botón para recibir tu foto al azar:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- PANEL DE ADMINISTRACIÓN (PRIVADO) ---
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📋 Ver / Editar / Borrar Fotos", callback_data="list_images")],
        [InlineKeyboardButton("🔙 Volver al inicio", callback_data="back_start")],
    ]
    await query.edit_message_text(
        "🛠️ *Panel de Administración*\n\n"
        "• Para **agregar** una foto nueva, simplemente envíamela por aquí con una descripción (el texto que acompañará a la foto).\n"
        "• Para cambiar probabilidades, textos o borrar, usa el botón de abajo.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# --- CAPTURAR FOTOS NUEVAS (SOLO ADMIN EN PRIVADO) ---
async def handle_admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID or update.effective_chat.type != "private":
        return

    photo = update.message.photo[-1]
    file_id = photo.file_id
    caption = update.message.caption or ""

    conn = sqlite3.connect("bot_rajona.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO images (file_id, weight, caption) VALUES (?, 1, ?)", (file_id, caption))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ ¡Foto agregada con éxito al sistema!\n"
        "• Peso por defecto: `1`\n"
        f"• Mensaje asignado: {caption if caption else '*(Sin texto)*'}",
        parse_mode="Markdown"
    )

# --- LOGICA: ENVIAR FOTO AL AZAR POR DM ---
async def send_random_image_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    conn = sqlite3.connect("bot_rajona.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_id, weight, caption FROM images")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        try:
            await context.bot.send_message(chat_id=user.id, text="⚠️ Aún no hay fotos configuradas en el bot.")
        except Exception:
            await query.edit_message_text("⚠️ No puedes recibir mensajes privados. Primero háblame al privado dándole a /start.")
        return

    file_ids = [row[1] for row in rows]
    weights = [row[2] for row in rows]
    captions = [row[3] for row in rows]

    chosen_file, chosen_caption, chosen_weight = random.choices(
        list(zip(file_ids, captions, weights)), weights=weights, k=1
    )[0]

    try:
        await context.bot.send_photo(
            chat_id=user.id,
            photo=chosen_file,
            caption=chosen_caption if chosen_caption else None
        )
        if query.message.chat.type != "private":
            await query.answer("¡Te he enviado tu foto por mensaje privado! 📩", show_alert=True)
    except Exception:
        if query.message.chat.type != "private":
            await query.answer("❌ No te pude enviar el DM. Tienes que iniciar una conversación privada conmigo primero (/start).", show_alert=True)
        else:
            await query.edit_message_text("❌ Hubo un error al enviarte la foto.")

# --- LISTAR, EDITAR Y BORRAR FOTOS (ADMIN) ---
async def list_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect("bot_rajona.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, weight, caption FROM images")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="admin_menu")]]
        await query.edit_message_text("No hay fotos registradas.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "📋 *Gestión de Fotos y Probabilidades:*\n\n"
    keyboard = []
    for row in rows:
        img_id, weight, caption = row
        short_caption = (caption[:15] + '...') if len(caption) > 15 else (caption or "Sin texto")
        text += f"🆔 ID: `{img_id}` | ⚖️ Peso: `{weight}` | 💬 {short_caption}\n"
        
        keyboard.append([
            InlineKeyboardButton(f"❌ Borrar {img_id}", callback_data=f"del_{img_id}"),
            InlineKeyboardButton(f"⚖️ Peso ID {img_id}", callback_data=f"editw_{img_id}"),
            InlineKeyboardButton(f"💬 Texto ID {img_id}", callback_data=f"editc_{img_id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver al Panel", callback_data="admin_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- MANEJADOR DE BOTONES ADMINISTRATIVOS ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "rajona_azur":
        await send_random_image_dm(update, context)
    elif data == "admin_menu":
        await admin_menu(update, context)
    elif data == "back_start":
        await start(update, context)
    elif data == "list_images":
        await list_images(update, context)
    elif data.startswith("del_"):
        img_id = data.split("_")[1]
        conn = sqlite3.connect("bot_rajona.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM images WHERE id = ?", (img_id,))
        conn.commit()
        conn.close()
        await query.answer("¡Foto eliminada!")
        await list_images(update, context)
    elif data.startswith("editw_"):
        img_id = data.split("_")[1]
        context.user_data["editing_weight_id"] = img_id
        await query.message.reply_text(f"✍️ Escribe el nuevo **número de peso** (ej: 1, 5, 10) para la imagen ID {img_id}:", parse_mode="Markdown")
        await query.answer()
    elif data.startswith("editc_"):
        img_id = data.split("_")[1]
        context.user_data["editing_caption_id"] = img_id
        await query.message.reply_text(f"✍️ Escribe el **nuevo texto** para la imagen ID {img_id} (o escribe 'ninguno'):", parse_mode="Markdown")
        await query.answer()

# --- MANEJADOR DE TEXTO ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or update.effective_chat.type != "private":
        return

    text = update.message.text

    if "editing_weight_id" in context.user_data:
        img_id = context.user_data["editing_weight_id"]
        try:
            new_weight = int(text)
            conn = sqlite3.connect("bot_rajona.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE images SET weight = ? WHERE id = ?", (new_weight, img_id))
            conn.commit()
            conn.close()
            
            del context.user_data["editing_weight_id"]
            await update.message.reply_text(f"✅ ¡Peso actualizado a `{new_weight}`!", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("⚠️ Introduce un número entero válido.")

    elif "editing_caption_id" in context.user_data:
        img_id = context.user_data["editing_caption_id"]
        new_caption = "" if text.lower() == "ninguno" else text
        
        conn = sqlite3.connect("bot_rajona.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE images SET caption = ? WHERE id = ?", (new_caption, img_id))
        conn.commit()
        conn.close()
        
        del context.user_data["editing_caption_id"]
        await update.message.reply_text(f"✅ ¡Texto actualizado!")

# --- COMANDO PANEL GRUPO ---
async def panel_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    keyboard = [[InlineKeyboardButton("🎲 Rajona al azar", callback_data="rajona_azur")]]
    await update.message.reply_text(
        "Panel interactivo de Rajona:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel_grupo))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_admin_photo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & filters.ChatType.PRIVATE, text_handler))

    print("Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
