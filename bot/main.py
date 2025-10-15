import logging
import os
from dotenv import load_dotenv
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

# Load env
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Bot config
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

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

# Customize options
SUGAR_OPTIONS = {
    "0": {"label": "គ្មានស្ករ (0%)", "price": 0},
    "25": {"label": "ស្ករតិច (25%)", "price": 0},
    "50": {"label": "ស្ករមធ្យម (50%)", "price": 0},
    "75": {"label": "ស្ករច្រើន (75%)", "price": 0},
    "100": {"label": "ស្ករពេញ (100%)", "price": 0},
}

ICE_OPTIONS = {
    "no": {"label": "គ្មានទឹកកក", "price": 0},
    "less": {"label": "ទឹកកកតិច", "price": 0},
    "normal": {"label": "ទឹកកកធម្មតា", "price": 0},
    "extra": {"label": "ទឹកកកច្រើន", "price": 0},
}

SIZE_OPTIONS = {
    "small": {"label": "តូច (S)", "price": 0},
    "medium": {"label": "មធ្យម (M)", "price": 0.5},
    "large": {"label": "ធំ (L)", "price": 1.0},
}

# Store carts and temp orders
user_carts = {}
temp_orders = {}

# Get cart
def get_cart(user_id):
    if user_id not in user_carts:
        user_carts[user_id] = []
    return user_carts[user_id]

# Get temp order
def get_temp_order(user_id):
    if user_id not in temp_orders:
        temp_orders[user_id] = {}
    return temp_orders[user_id]

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
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_{category}_{item_name}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_menu")])
    keyboard.append([InlineKeyboardButton("🛒 មើលកន្ត្រក", callback_data="view_cart")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 ម៉ឺនុយ {category_name}៖\n\n"
        "ជ្រើសរើសដើម្បីបញ្ជាទិញ៖",
        reply_markup=reply_markup
    )

# Show customization
async def show_customization(update: Update, context: ContextTypes.DEFAULT_TYPE, category, item_name):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    item_info = MENU[category][item_name]
    
    # Init temp order
    temp_order = get_temp_order(user_id)
    temp_order['category'] = category
    temp_order['item_name'] = item_name
    temp_order['base_price'] = item_info['price']
    temp_order['emoji'] = item_info['emoji']
    
    # Set defaults
    if 'size' not in temp_order:
        temp_order['size'] = 'medium'
    if 'sugar' not in temp_order:
        temp_order['sugar'] = '50'
    if 'ice' not in temp_order:
        temp_order['ice'] = 'normal'
    if 'quantity' not in temp_order:
        temp_order['quantity'] = 1
    
    await show_order_page(update, context)

# Show order page
async def show_order_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    temp_order = get_temp_order(user_id)
    
    # Calculate price
    base_price = temp_order['base_price']
    size_price = SIZE_OPTIONS[temp_order['size']]['price']
    quantity = temp_order['quantity']
    total_price = (base_price + size_price) * quantity
    
    # Build message
    text = f"{temp_order['emoji']} {temp_order['item_name']}\n\n"
    text += f"📏 ទំហំ: {SIZE_OPTIONS[temp_order['size']]['label']}\n"
    text += f"🍬 ស្ករ: {SUGAR_OPTIONS[temp_order['sugar']]['label']}\n"
    text += f"🧊 ទឹកកក: {ICE_OPTIONS[temp_order['ice']]['label']}\n"
    text += f"🔢 ចំនួន: {quantity}\n\n"
    text += f"💰 តម្លៃ: ${total_price:.2f}"
    
    keyboard = [
        [
            InlineKeyboardButton("📏 ទំហំ", callback_data="customize_size"),
            InlineKeyboardButton("🍬 ស្ករ", callback_data="customize_sugar"),
        ],
        [
            InlineKeyboardButton("🧊 ទឹកកក", callback_data="customize_ice"),
            InlineKeyboardButton("🔢 ចំនួន", callback_data="customize_quantity"),
        ],
        [
            InlineKeyboardButton("✅ បញ្ចូលកន្ត្រក", callback_data="confirm_add"),
            InlineKeyboardButton("❌ បោះបង់", callback_data=f"category_{temp_order['category']}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Customize size
async def customize_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for size_key, size_info in SIZE_OPTIONS.items():
        price_text = f" (+${size_info['price']:.2f})" if size_info['price'] > 0 else ""
        keyboard.append([InlineKeyboardButton(
            f"{size_info['label']}{price_text}",
            callback_data=f"set_size_{size_key}"
        )])
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_order")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("📏 ជ្រើសរើសទំហំ:", reply_markup=reply_markup)

# Customize sugar
async def customize_sugar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for sugar_key, sugar_info in SUGAR_OPTIONS.items():
        keyboard.append([InlineKeyboardButton(
            sugar_info['label'],
            callback_data=f"set_sugar_{sugar_key}"
        )])
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_order")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🍬 ជ្រើសរើសកម្រិតស្ករ:", reply_markup=reply_markup)

# Customize ice
async def customize_ice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for ice_key, ice_info in ICE_OPTIONS.items():
        keyboard.append([InlineKeyboardButton(
            ice_info['label'],
            callback_data=f"set_ice_{ice_key}"
        )])
    keyboard.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_order")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🧊 ជ្រើសរើសទឹកកក:", reply_markup=reply_markup)

# Customize quantity
async def customize_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    temp_order = get_temp_order(user_id)
    current_qty = temp_order.get('quantity', 1)
    
    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data="qty_decrease"),
            InlineKeyboardButton(f"{current_qty}", callback_data="qty_current"),
            InlineKeyboardButton("➕", callback_data="qty_increase"),
        ],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_order")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"🔢 ចំនួន: {current_qty}", reply_markup=reply_markup)

# Confirm add to cart
async def confirm_add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ បានបញ្ចូលហើយ!")
    
    user_id = query.from_user.id
    cart = get_cart(user_id)
    temp_order = get_temp_order(user_id)
    
    # Add to cart
    cart.append({
        "name": temp_order['item_name'],
        "base_price": temp_order['base_price'],
        "emoji": temp_order['emoji'],
        "category": temp_order['category'],
        "size": temp_order['size'],
        "sugar": temp_order['sugar'],
        "ice": temp_order['ice'],
        "quantity": temp_order['quantity'],
        "total_price": (temp_order['base_price'] + SIZE_OPTIONS[temp_order['size']]['price']) * temp_order['quantity']
    })
    
    # Clear temp
    temp_orders[user_id] = {}
    
    # Go back to category
    await show_category(update, context, temp_order['category'])

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
        cart_text += f"{idx}. {item['emoji']} {item['name']}\n"
        cart_text += f"   📏 {SIZE_OPTIONS[item['size']]['label']} | "
        cart_text += f"🍬 {item['sugar']}% | "
        cart_text += f"🧊 {ICE_OPTIONS[item['ice']]['label']}\n"
        cart_text += f"   🔢 x{item['quantity']} = ${item['total_price']:.2f}\n\n"
        total += item['total_price']
    
    cart_text += f"💰 សរុប៖ ${total:.2f}"
    
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
    total = sum(item['total_price'] for item in cart)
    
    # Generate ID
    order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # User confirmation
    delivery_text = "មកយកផ្ទាល់" if delivery_method == "pickup" else "ដឹកជញ្ជូន"
    order_text = f"🎉 បានបញ្ជាទិញដោយជោគជ័យ!\n\n"
    order_text += f"📝 លេខកម្មង់៖ {order_id}\n"
    order_text += f"📦 វិធី៖ {delivery_text}\n\n"
    order_text += "ទំនិញ៖\n"
    
    for idx, item in enumerate(cart, 1):
        order_text += f"{idx}. {item['emoji']} {item['name']}\n"
        order_text += f"   📏 {SIZE_OPTIONS[item['size']]['label']} | "
        order_text += f"🍬 {item['sugar']}% | "
        order_text += f"🧊 {ICE_OPTIONS[item['ice']]['label']}\n"
        order_text += f"   🔢 x{item['quantity']} = ${item['total_price']:.2f}\n\n"
    
    order_text += f"💰 សរុប៖ ${total:.2f}\n\n"
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
        admin_text += f"{idx}. {item['emoji']} {item['name']}\n"
        admin_text += f"   📏 {SIZE_OPTIONS[item['size']]['label']} | "
        admin_text += f"🍬 {item['sugar']}% | "
        admin_text += f"🧊 {ICE_OPTIONS[item['ice']]['label']}\n"
        admin_text += f"   🔢 x{item['quantity']} = ${item['total_price']:.2f}\n\n"
    
    admin_text += f"💰 សរុប៖ ${total:.2f}"
    
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
    user_id = query.from_user.id
    
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
    
    elif data.startswith("select_"):
        parts = data.replace("select_", "").split("_", 1)
        category = parts[0]
        item_name = parts[1]
        await show_customization(update, context, category, item_name)
    
    elif data == "back_to_order":
        await show_order_page(update, context)
    
    elif data == "customize_size":
        await customize_size(update, context)
    
    elif data == "customize_sugar":
        await customize_sugar(update, context)
    
    elif data == "customize_ice":
        await customize_ice(update, context)
    
    elif data == "customize_quantity":
        await customize_quantity(update, context)
    
    elif data.startswith("set_size_"):
        size = data.replace("set_size_", "")
        temp_orders[user_id]['size'] = size
        await show_order_page(update, context)
    
    elif data.startswith("set_sugar_"):
        sugar = data.replace("set_sugar_", "")
        temp_orders[user_id]['sugar'] = sugar
        await show_order_page(update, context)
    
    elif data.startswith("set_ice_"):
        ice = data.replace("set_ice_", "")
        temp_orders[user_id]['ice'] = ice
        await show_order_page(update, context)
    
    elif data == "qty_increase":
        temp_orders[user_id]['quantity'] = temp_orders[user_id].get('quantity', 1) + 1
        await customize_quantity(update, context)
    
    elif data == "qty_decrease":
        current = temp_orders[user_id].get('quantity', 1)
        if current > 1:
            temp_orders[user_id]['quantity'] = current - 1
        await customize_quantity(update, context)
    
    elif data == "qty_current":
        await query.answer()
    
    elif data == "confirm_add":
        await confirm_add_to_cart(update, context)
    
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
    print("🤖 Bot bot pg ta run hz b...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()