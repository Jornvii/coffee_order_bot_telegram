import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from datetime import datetime

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Bot config
BOT_TOKEN = os.getenv("BOT_TOKEN")
USERNAME = os.getenv("USERNAME")

# Menu
MENU = {
    "coffee": {
        "Espresso": {"price": 2.50, "emoji": "☕"},
        "Cappuccino": {"price": 3.50, "emoji": "☕"},
        "Latte": {"price": 4.00, "emoji": "☕"},
        "Americano": {"price": 3.00, "emoji": "☕"},
    },
    "food": {
        "Croissant": {"price": 3.50, "emoji": "🥐"},
        "Sandwich": {"price": 5.50, "emoji": "🥪"},
        "Bagel": {"price": 4.00, "emoji": "🥯"},
        "Muffin": {"price": 3.00, "emoji": "🧁"},
    },
    "drinks": {
        "Orange Juice": {"price": 3.00, "emoji": "🍊"},
        "Smoothie": {"price": 4.50, "emoji": "🥤"},
        "Iced Tea": {"price": 2.50, "emoji": "🧃"},
        "Water": {"price": 1.00, "emoji": "💧"},
    }
}

# Store carts
user_carts = {}

# Get cart
def get_cart(user_id):
    if user_id not in user_carts:
        user_carts[user_id] = []
    return user_carts[user_id]

# Start menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("☕ កាហ្វេ", callback_data="category_coffee")],
        [InlineKeyboardButton("🍽️ អាហារ", callback_data="category_food")],
        [InlineKeyboardButton("🥤 ភេសជ្ជៈ", callback_data="category_drinks")],
        [InlineKeyboardButton("🛒 មើលកន្ត្រក", callback_data="view_cart")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "☕ សូមស្វាគមន៍មកកាហ្វេរបស់យើង! ☕\n\n"
        "សូមរកមើលម៉ឺនុយ និងបញ្ជាទិញ៖\n"
        "ជ្រើសរើសប្រភេទខាងក្រោម៖",
        reply_markup=reply_markup
    )

# Show items
async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    query = update.callback_query
    await query.answer()
    
    category_names = {
        "coffee": "កាហ្វេ",
        "food": "អាហារ",
        "drinks": "ភេសជ្ជៈ"
    }
    category_name = category_names.get(category, category)
    items = MENU[category]
    
    keyboard = []
    for item_name, item_info in items.items():
        emoji = item_info['emoji']
        price = item_info['price']
        button_text = f"{emoji} {item_name} - ${price:.2f}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"add_{category}_{item_name}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_menu")])
    keyboard.append([InlineKeyboardButton("🛒 មើលកន្ត្រក", callback_data="view_cart")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 ម៉ឺនុយ {category_name}៖\n\n"
        "ជ្រើសរើសដើម្បីបញ្ចូលទៅកន្ត្រក៖",
        reply_markup=reply_markup
    )

# Add to cart
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE, category, item_name):
    query = update.callback_query
    await query.answer("✅ បានបញ្ចូលហើយ!")
    
    user_id = query.from_user.id
    cart = get_cart(user_id)
    
    item_info = MENU[category][item_name]
    cart.append({
        "name": item_name,
        "price": item_info['price'],
        "emoji": item_info['emoji'],
        "category": category
    })
    
    await show_category(update, context, category)

# View cart
async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    cart = get_cart(user_id)
    
    if not cart:
        keyboard = [[InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🛒 កន្ត្រករបស់អ្នកទទេ!\n\n"
            "សូមចាប់ផ្តើមបញ្ចូលទំនិញពីម៉ឺនុយ។",
            reply_markup=reply_markup
        )
        return
    
    # Format cart
    cart_text = "🛒 កន្ត្រករបស់អ្នក៖\n\n"
    total = 0
    
    for idx, item in enumerate(cart, 1):
        cart_text += f"{idx}. {item['emoji']} {item['name']} - ${item['price']:.2f}\n"
        total += item['price']
    
    cart_text += f"\n💰 សរុប៖ ${total:.2f}"
    
    keyboard = [
        [InlineKeyboardButton("✅ បញ្ជាទិញ", callback_data="checkout")],
        [InlineKeyboardButton("🗑️ លុបកន្ត្រក", callback_data="clear_cart")],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(cart_text, reply_markup=reply_markup)

# Clear cart
async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🗑️ បានលុបហើយ!")
    
    user_id = query.from_user.id
    user_carts[user_id] = []
    
    await view_cart(update, context)

# Checkout
async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    cart = get_cart(user_id)
    
    if not cart:
        await query.edit_message_text("🛒 កន្ត្រករបស់អ្នកទទេ!")
        return
    
    keyboard = [
        [InlineKeyboardButton("🏪 មកយកផ្ទាល់", callback_data="delivery_pickup")],
        [InlineKeyboardButton("🚚 ដឹកជញ្ជូន", callback_data="delivery_delivery")],
        [InlineKeyboardButton("⬅️ ត្រលប់កន្ត្រក", callback_data="view_cart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📦 តើអ្នកចង់បានវិធីណា?",
        reply_markup=reply_markup
    )

# Process order
async def process_order(update: Update, context: ContextTypes.DEFAULT_TYPE, delivery_method):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = query.from_user
    cart = get_cart(user_id)
    
    if not cart:
        await query.edit_message_text("🛒 កន្ត្រករបស់អ្នកទទេ!")
        return
    
    # Calculate total
    total = sum(item['price'] for item in cart)
    
    # Generate ID
    order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # User confirmation
    delivery_text = "មកយកផ្ទាល់" if delivery_method == "pickup" else "ដឹកជញ្ជូន"
    order_text = f"🎉 បានបញ្ជាទិញដោយជោគជ័យ!\n\n"
    order_text += f"📝 លេខកម្មង់៖ {order_id}\n"
    order_text += f"📦 វិធី៖ {delivery_text}\n\n"
    order_text += "ទំនិញ៖\n"
    
    for idx, item in enumerate(cart, 1):
        order_text += f"{idx}. {item['emoji']} {item['name']} - ${item['price']:.2f}\n"
    
    order_text += f"\n💰 សរុប៖ ${total:.2f}\n\n"
    order_text += "សូមអរគុណសម្រាប់ការបញ្ជាទិញ! យើងនឹងរៀបចំឲ្យបាន។ ☕"
    
    keyboard = [[InlineKeyboardButton("🏠 ត្រលប់ទៅម៉ឺនុយ", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(order_text, reply_markup=reply_markup)
    
    # Admin notification
    admin_text = f"🔔 កម្មង់ថ្មី!\n\n"
    admin_text += f"📝 លេខកម្មង់៖ {order_id}\n"
    admin_text += f"👤 អតិថិជន៖ {user.first_name} {user.last_name or ''}\n"
    admin_text += f"🆔 User ID៖ {user_id}\n"
    admin_text += f"👤 Username៖ @{user.username or 'N/A'}\n"
    admin_text += f"📦 វិធី៖ {delivery_text}\n\n"
    admin_text += "ទំនិញ៖\n"
    
    for idx, item in enumerate(cart, 1):
        admin_text += f"{idx}. {item['emoji']} {item['name']} - ${item['price']:.2f}\n"
    
    admin_text += f"\n💰 សរុប៖ ${total:.2f}"
    
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text)
    except Exception as e:
        logging.error(f"Admin notify failed: {e}")
    
    # Clear cart
    user_carts[user_id] = []

# Button handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("☕ កាហ្វេ", callback_data="category_coffee")],
            [InlineKeyboardButton("🍽️ អាហារ", callback_data="category_food")],
            [InlineKeyboardButton("🥤 ភេសជ្ជៈ", callback_data="category_drinks")],
            [InlineKeyboardButton("🛒 មើលកន្ត្រក", callback_data="view_cart")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "☕ សូមស្វាគមន៍មកកាហ្វេរបស់យើង! ☕\n\n"
            "សូមរកមើលម៉ឺនុយ និងបញ្ជាទិញ៖\n"
            "ជ្រើសរើសប្រភេទខាងក្រោម៖",
            reply_markup=reply_markup
        )
    
    elif data.startswith("category_"):
        category = data.replace("category_", "")
        await show_category(update, context, category)
    
    elif data.startswith("add_"):
        parts = data.replace("add_", "").split("_", 1)
        category = parts[0]
        item_name = parts[1]
        await add_to_cart(update, context, category, item_name)
    
    elif data == "view_cart":
        await view_cart(update, context)
    
    elif data == "clear_cart":
        await clear_cart(update, context)
    
    elif data == "checkout":
        await checkout(update, context)
    
    elif data.startswith("delivery_"):
        delivery_method = data.replace("delivery_", "")
        await process_order(update, context, delivery_method)

# Main
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Run bot
    print("🤖 Bot កំពុងដំណើរការ...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()