import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Import menu and options (your existing files)
from menu_order.menu_items import MENU
from menu_order.option_item import SIZE_OPTIONS, SUGAR_OPTIONS, ICE_OPTIONS



load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
BOT_TOKEN = os.getenv("BOT_TOKEN")          
BOT_USERNAME = os.getenv("BOT_USERNAME")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
# ADMIN_CHAT_ID = ( int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID and ADMIN_CHAT_ID.isdigit() else None )
GROUP_CHAT_ID = int(GROUP_CHAT_ID) if GROUP_CHAT_ID and GROUP_CHAT_ID.lstrip("-").isdigit() else None

# In-memory storage
user_carts = {}  # user_id -> list
temp_orders = {}  # user_id -> dict


# --- Helpers ---
def get_cart(uid: int):
    if uid not in user_carts:
        user_carts[uid] = []
    return user_carts[uid]


def get_temp(uid: int):
    if uid not in temp_orders:
        temp_orders[uid] = {}
    return temp_orders[uid]


def _ensure_defaults(t: dict):
    """Ensure temp-order dictionary has required keys with defaults."""
    t.setdefault("category", "")
    t.setdefault("item_name", "")
    t.setdefault("emoji", "")
    t.setdefault("base_price", 0.0)
    t.setdefault("size", "medium")
    t.setdefault("sugar", "50")
    t.setdefault("ice", "normal")
    t.setdefault("quantity", 1)


# --- Commands / Entry points ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # safe message retrieval when called from callback or command
    msg = getattr(update, "message", None) or (
        getattr(update, "callback_query", None) and update.callback_query.message
    )
    if msg is None:
        return

    keyboard = [
        [InlineKeyboardButton("☕ កាហ្វេ", callback_data="category_coffee")],
        [InlineKeyboardButton("🍽️ អាហារ", callback_data="category_food")],
        [InlineKeyboardButton("🥤 ភេសជ្ជៈ", callback_data="category_drinks")],
        [InlineKeyboardButton("🛒 មើលកន្ត្រក", callback_data="view_cart")],
    ]
    await msg.reply_text(
        "☕ សូមស្វាគមន៍មកកាហ្វេរបស់យើង!\n\nជ្រើសរើសប្រភេទខាងក្រោម៖",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None:
        return
    kb = []
    if ADMIN_USERNAME:
        kb.append(
            [
                InlineKeyboardButton(
                    "📩 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}"
                )
            ]
        )
    kb.append([InlineKeyboardButton("🏠 Back", callback_data="back_to_menu")])
    await msg.reply_text("💬 Need help?", reply_markup=InlineKeyboardMarkup(kb))


# --- Category listing ---
async def show_category(update, context, category: str):
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    items = MENU.get(category, {})
    if not items:
        await query.edit_message_text("❌ មិនមានទំនិញនេះទេ")
        return

    kb = []
    for name, info in items.items():
        kb.append(
            [
                InlineKeyboardButton(
                    f"{info['emoji']} {name} - ${info['price']:.2f}",
                    callback_data=f"select_{category}_{name}",
                )
            ]
        )
    kb.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_menu")])
    await query.edit_message_text(
        f"📋 ម៉ឺនុយ {category}៖", reply_markup=InlineKeyboardMarkup(kb)
    )


# --- Start customizing an item ---
async def show_customization(update, context, category: str, item_name: str):
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    items = MENU.get(category, {})
    if item_name not in items:
        await query.edit_message_text("❌ មិនមានទំនិញនេះទេ")
        return

    item = items[item_name]
    uid = query.from_user.id
    t = get_temp(uid)
    # set up temp order defaults
    t.update(
        {
            "category": category,
            "item_name": item_name,
            "emoji": item.get("emoji", ""),
            "base_price": item.get("price", 0.0),
            "size": t.get("size", "medium"),
            "sugar": t.get("sugar", "50"),
            "ice": t.get("ice", "normal"),
            "quantity": t.get("quantity", 1),
        }
    )
    await refresh_order_view(update, context)


# --- Centralized order view (single source of truth) ---
async def refresh_order_view(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    uid = query.from_user.id
    t = get_temp(uid)
    _ensure_defaults(t)

    # Calculate total price
    size_add = SIZE_OPTIONS.get(t["size"], {}).get("price", 0.0)
    total = (t["base_price"] + size_add) * t["quantity"]

    # Build order summary text
    text = f"{t['emoji']} {t['item_name']}\n"
    text += f"📏 ទំហំ: {SIZE_OPTIONS.get(t['size'], {}).get('label', t['size'])}\n"

    # Only include sugar and ice for non-food items
    if t["category"] != "food":
        text += (
            f"🍬 ស្ករ: {SUGAR_OPTIONS.get(t['sugar'], {}).get('label', t['sugar'])}\n"
        )
        text += f"🧊 ទឹកកក: {ICE_OPTIONS.get(t['ice'], {}).get('label', t['ice'])}\n"

    text += f"🔢 ចំនួន: {t['quantity']}\n\n💰 តម្លៃសរុប: ${total:.2f}"

    # --- Keyboard Layout ---
    kb = []

    # Always show size + quantity
    row1 = [InlineKeyboardButton("📏 ទំហំ", callback_data="customize_size")]

    # Add sugar/ice buttons only if not food
    if t["category"] != "food":
        row1.append(InlineKeyboardButton("🍬 ស្ករ", callback_data="customize_sugar"))
        row2 = [
            InlineKeyboardButton("🧊 ទឹកកក", callback_data="customize_ice"),
            InlineKeyboardButton("🔢 ចំនួន", callback_data="customize_quantity"),
        ]
        kb.append(row1)
        kb.append(row2)
    else:
        # For food: just show size and quantity
        row1.append(InlineKeyboardButton("🔢 ចំនួន", callback_data="customize_quantity"))
        kb.append(row1)

    # Confirm & back buttons
    kb.append(
        [
            InlineKeyboardButton("✅ បញ្ចូលកន្ត្រក", callback_data="confirm_add"),
            InlineKeyboardButton(
                "⬅️ ត្រលប់ក្រោយ", callback_data=f"category_{t['category']}"
            ),
        ]
    )

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))


# --- Quantity UI (live) ---
async def show_quantity_editor(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    uid = query.from_user.id
    t = get_temp(uid)
    _ensure_defaults(t)
    qty = t["quantity"]

    kb = [
        [
            InlineKeyboardButton("➖", callback_data="qty_dec"),
            InlineKeyboardButton(f"{qty}", callback_data="qty_none"),
            InlineKeyboardButton("➕", callback_data="qty_inc"),
        ],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_order")],
    ]
    await query.edit_message_text(
        f"🔢 កែចំនួន៖ {qty}", reply_markup=InlineKeyboardMarkup(kb)
    )


async def quantity_change(update, context, op: str):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    uid = query.from_user.id
    t = get_temp(uid)
    _ensure_defaults(t)
    if op == "inc":
        # optional guard: max limit
        t["quantity"] = t.get("quantity", 1) + 1
    elif op == "dec":
        if t.get("quantity", 1) > 1:
            t["quantity"] = t.get("quantity", 1) - 1

    # Re-render the quantity editor so user sees the number change immediately
    await show_quantity_editor(update, context)


# --- Size / Sugar / Ice editors (show choices) ---
async def show_size_editor(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    uid = query.from_user.id
    t = get_temp(uid)
    current = t.get("size", "medium")

    kb = []
    # Show currently selected size at the top
    current_label = SIZE_OPTIONS.get(current, {}).get("label", current)
    kb.append(
        [InlineKeyboardButton(f"✅ កំពុងជ្រើសរើស: {current_label}", callback_data="none")]
    )

    for key, val in SIZE_OPTIONS.items():
        if key == current:
            continue
        price_text = f" +${val['price']:.2f}" if val.get("price", 0) else ""
        kb.append(
            [
                InlineKeyboardButton(
                    f"{val['label']}{price_text}", callback_data=f"set_size_{key}"
                )
            ]
        )
    kb.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_order")])
    await query.edit_message_text("📏 ជ្រើសទំហំ:", reply_markup=InlineKeyboardMarkup(kb))


async def show_sugar_editor(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    uid = query.from_user.id
    t = get_temp(uid)
    current = t.get("sugar", "50")

    kb = []
    kb.append(
        [
            InlineKeyboardButton(
                f"✅ កំពុងជ្រើសរើស: {SUGAR_OPTIONS.get(current, {}).get('label', current)}",
                callback_data="none",
            )
        ]
    )
    for key, val in SUGAR_OPTIONS.items():
        if key == current:
            continue
        kb.append(
            [InlineKeyboardButton(val["label"], callback_data=f"set_sugar_{key}")]
        )
    kb.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_order")])
    await query.edit_message_text("🍬 ជ្រើសស្ករ:", reply_markup=InlineKeyboardMarkup(kb))


async def show_ice_editor(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    uid = query.from_user.id
    t = get_temp(uid)
    current = t.get("ice", "normal")

    kb = []
    kb.append(
        [
            InlineKeyboardButton(
                f"✅ កំពុងជ្រើសរើស: {ICE_OPTIONS.get(current, {}).get('label', current)}",
                callback_data="none",
            )
        ]
    )
    for key, val in ICE_OPTIONS.items():
        if key == current:
            continue
        kb.append([InlineKeyboardButton(val["label"], callback_data=f"set_ice_{key}")])
    kb.append([InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_order")])
    await query.edit_message_text("🧊 ជ្រើសទឹកកក:", reply_markup=InlineKeyboardMarkup(kb))


# --- Confirm add & Cart flow ---
async def confirm_add(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer("✅ Added!")
    uid = query.from_user.id
    cart = get_cart(uid)
    t = get_temp(uid)
    _ensure_defaults(t)

    size_price = SIZE_OPTIONS.get(t["size"], {}).get("price", 0.0)
    total = (t["base_price"] + size_price) * t["quantity"]
    cart.append({**t, "total_price": total})

    # clear temp order for that user
    temp_orders[uid] = {}
    # go back to the category listing where item was selected
    await show_category(update, context, t["category"])


async def view_cart(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    uid = query.from_user.id
    cart = get_cart(uid)
    if not cart:
        await query.edit_message_text(
            "🛒 កន្ត្រកទទេ!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_menu")]]
            ),
        )
        return

    text = "🛒 កន្ត្រករបស់អ្នក:\n\n"
    total_all = 0.0
    for i, it in enumerate(cart, 1):
        text += f"{i}. {it.get('emoji','')} {it.get('item_name','')} x{it.get('quantity',1)} = ${it.get('total_price',0):.2f}\n"
        total_all += it.get("total_price", 0.0)
    text += f"\n💰 សរុប: ${total_all:.2f}"

    kb = [
        [InlineKeyboardButton("✅ បញ្ជាទិញ", callback_data="checkout")],
        [InlineKeyboardButton("🗑️ លុបកន្ត្រក", callback_data="clear_cart")],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="back_to_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))


async def clear_cart(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer("🗑️ Cleared!")
    user_carts[query.from_user.id] = []
    await view_cart(update, context)


# --- Checkout / process order ---
async def checkout(update, context):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    kb = [
        [InlineKeyboardButton("🏪 មកយកផ្ទាល់", callback_data="delivery_pickup")],
        [InlineKeyboardButton("🚚 ដឹកជញ្ជូន", callback_data="delivery_delivery")],
        [InlineKeyboardButton("⬅️ ត្រលប់ក្រោយ", callback_data="view_cart")],
    ]
    await query.edit_message_text(
        "📦 ជ្រើសរើសវិធី:", reply_markup=InlineKeyboardMarkup(kb)
    )


async def process_order(update, context, method: str):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    uid = query.from_user.id
    cart = get_cart(uid)
    if not cart:
        await query.edit_message_text("🛒 កន្ត្រកទទេ!")
        return

    total_all = sum(it.get("total_price", 0) for it in cart)
    order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
    delivery_text = "មកយកផ្ទាល់" if method == "pickup" else "ដឹកជញ្ជូន"

    # Build detailed order text
    order_detail_text = f"🧾 ព័ត៌មានការកម្មង់ #{order_id}\n"
    order_detail_text += f"📦 វិធី: {delivery_text}\n"
    order_detail_text += f"👤 អ្នកកម្មង់: {query.from_user.full_name}\n"
    order_detail_text += (
        f"🕒 ពេលវេលា: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )

    for i, item in enumerate(cart, 1):
        order_detail_text += (
            f"{i}. {item.get('emoji','')} {item.get('item_name','')}\n"
            f"   📏 ទំហំ: {SIZE_OPTIONS.get(item['size'], {}).get('label', item['size'])}\n"
            f"   🍬 ស្ករ: {SUGAR_OPTIONS.get(item['sugar'], {}).get('label', item['sugar'])}\n"
            f"   🧊 ទឹកកក: {ICE_OPTIONS.get(item['ice'], {}).get('label', item['ice'])}\n"
            f"   🔢 ចំនួន: {item['quantity']}\n"
            f"   💰 តម្លៃសរុប: ${item['total_price']:.2f}\n\n"
        )

    order_detail_text += f"💰 សរុបសរុប: ${total_all:.2f}\n"
    order_detail_text += "🙏 សូមអរគុណសម្រាប់ការកម្មង់របស់អ្នក!"

    # Send order confirmation to user (instead of just a simple message)
    await query.edit_message_text(
        order_detail_text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 ត្រលប់ទៅម៉ឺនុយ", callback_data="back_to_menu")]]
        ),
    )

    # Build detailed notification for admin and group
    notify_text = (
        f"🔔 កម្មង់ថ្មី #{order_id}\n"
        f"👤 អ្នកកម្មង់: {query.from_user.full_name}\n"
        f"📦 វិធី: {delivery_text}\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )

    for i, item in enumerate(cart, 1):
        notify_text += (
            f"{i}. {item.get('emoji','')} {item.get('item_name','')}\n"
            f"   📏 ទំហំ: {SIZE_OPTIONS.get(item['size'], {}).get('label', item['size'])}\n"
        )
        # Show sugar & ice only for non-food items
        if item.get("category") != "food":
            notify_text += (
                f"   🍬 ស្ករ: {SUGAR_OPTIONS.get(item['sugar'], {}).get('label', item['sugar'])}\n"
                f"   🧊 ទឹកកក: {ICE_OPTIONS.get(item['ice'], {}).get('label', item['ice'])}\n"
            )
        notify_text += (
            f"   🔢 ចំនួន: {item['quantity']}\n"
            f"   💰 ${item['total_price']:.2f}\n\n"
        )

    notify_text += f"💰 សរុបសរុប: ${total_all:.2f}\n"

    # Send to group chat
    if GROUP_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=notify_text)
        except Exception as e:
            logging.error(f"Failed to notify group {GROUP_CHAT_ID}: {e}")

    # Clear the user cart after confirmation
    user_carts[uid] = []


# --- Main callback dispatcher ---
async def button_callback(update, context):
    query = update.callback_query
    if query is None:
        return
    data = query.data
    uid = query.from_user.id

    # navigation
    if data == "back_to_menu":
        await start(update, context)
        return

    if data.startswith("category_"):
        await show_category(update, context, data.split("_", 1)[1])
        return

    if data.startswith("select_"):
        # select_{category}_{item_name}   (split only first two underscores)
        _, category, item = data.split("_", 2)
        await show_customization(update, context, category, item)
        return

    # size flow
    if data == "customize_size":
        await show_size_editor(update, context)
        return
    if data.startswith("set_size_"):
        # set and refresh full order view
        t = get_temp(uid)
        t["size"] = data.split("_", 2)[2]
        await refresh_order_view(update, context)
        return

    # sugar flow
    if data == "customize_sugar":
        await show_sugar_editor(update, context)
        return
    if data.startswith("set_sugar_"):
        t = get_temp(uid)
        t["sugar"] = data.split("_", 2)[2]
        await refresh_order_view(update, context)
        return

    # ice flow
    if data == "customize_ice":
        await show_ice_editor(update, context)
        return
    if data.startswith("set_ice_"):
        t = get_temp(uid)
        t["ice"] = data.split("_", 2)[2]
        await refresh_order_view(update, context)
        return

    # quantity flow
    if data == "customize_quantity":
        await show_quantity_editor(update, context)
        return
    if data == "qty_inc":
        await quantity_change(update, context, "inc")
        return
    if data == "qty_dec":
        await quantity_change(update, context, "dec")
        return
    if data == "back_to_order":
        await refresh_order_view(update, context)
        return

    # confirm add
    if data == "confirm_add":
        await confirm_add(update, context)
        return

    # cart actions
    if data == "view_cart":
        await view_cart(update, context)
        return
    if data == "clear_cart":
        await clear_cart(update, context)
        return

    # checkout and orders
    if data == "checkout":
        await checkout(update, context)
        return
    if data.startswith("delivery_"):
        await process_order(update, context, data.split("_", 1)[1])
        return

    # fallback
    await query.answer("❓ មិនស្គាល់សកម្មភាព")
