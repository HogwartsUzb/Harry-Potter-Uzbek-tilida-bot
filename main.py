import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Yangilangan majburiy obuna kanallari ro'yxati
REQUIRED_CHANNELS = [
    {"name": "Garri Potter Uzbek", "username": "@HarryPotter_Uzbek", "url": "https://t.me/HarryPotter_Uzbek"},
    {"name": "Premium Starlight", "username": "@premium_starlight", "url": "https://t.me/premium_starlight"}
]
CHANNEL_USERNAME = "@HarryPotter_Uzbek" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# FSM
class AdminState(StatesGroup):
    waiting_for_password = State()
    waiting_for_admin_video = State()
    waiting_for_admin_book = State()  

# --- KLAVIATURA TUGMALARI ---
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="🎬 Kino ko'rish"), KeyboardButton(text="📚 Kitob o'qish")],
        [KeyboardButton(text="👥 Do'stlarni taklif qilish")],
        [KeyboardButton(text="🔒 Admin Panel")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Admin inline menu
def get_admin_inline_keyboard():
    kb = [
        [InlineKeyboardButton(text="📊 Top Taklifchilar (Top 10)", callback_data="admin_top_10")],
        [InlineKeyboardButton(text="🔑 Kino ID sini olish", callback_data="admin_get_file_id")],
        [InlineKeyboardButton(text="📘 Kitob ID sini olish", callback_data="admin_get_book_id")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- MAJBURIY OBUNANI TEKSHIRISH FUNKSIYASI ---
async def check_sub(user_id: int) -> bool:
    """Foydalanuvchi barcha majburiy kanallarga a'zo ekanligini tekshiradi"""
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["username"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            print(f"❌ Kanal tekshirishda xatolik ({channel['username']}): {e}")
            return False
    return True

# --- MAJBURIY OBUNA INLINE MENYUSI ---
def get_sub_keyboard():
    kb = []
    for channel in REQUIRED_CHANNELS:
        kb.append([InlineKeyboardButton(text=f"📣 {channel['name']}", url=channel['url'])])
    kb.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# --- /START BUYRUG'I ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    try:
        user_check = supabase.table("users").select("*").eq("telegram_id", user_id).execute()
        if not user_check.data:
            supabase.table("users").insert({
                "telegram_id": user_id,
                "username": username,
                "full_name": full_name,
                "invite_link": None,
                "referred_count": 0
            }).execute()
    except Exception as e:
        print(f"❌ Supabase start xatoligi: {e}")

    # Obunani tekshirish
    if not await check_sub(user_id):
        await message.answer(
            f"Salom, {full_name}! ⚡\nBotdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'lishingiz shart. "
            f"Iltimos, quyidagi kanallarga a'zo bo'lib, so'ng tekshirish tugmasini bosing:",
            reply_markup=get_sub_keyboard()
        )
        return

    await message.answer(
        f"Salom, {full_name}! Garri Potter virtual olamiga xush kelibsiz! ✨\n"
        f"Kino ko'rish yoki kitob o'qish uchun quyidagi tugmalardan foydalaning.",
        reply_markup=get_main_keyboard()
    )

# Obunani inline tugma orqali tekshirish handler'i
@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_sub(user_id):
        await callback.answer("🎉 Rahmat! Obuna muvaffaqiyatli tekshirildi.", show_alert=True)
        await callback.message.delete()
        await callback.message.answer(
            "✨ Garri Potter virtual olamiga xush kelibsiz!\nKerakli bo'limni tanlang:",
            reply_markup=get_main_keyboard()
        )
    else:
        await callback.answer("❌ Siz hali barcha kanallarga a'zo bo'lmadingiz! Iltimos, qaytadan tekshiring.", show_alert=True)


# --- DO'STLARNI TAKLIF QILISH TUGMASI ---
@dp.message(F.text == "👥 Do'stlarni taklif qilish")
async def invite_friends(message: types.Message):
    user_id = message.from_user.id
    
    if not await check_sub(user_id):
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'lishingiz shart:", reply_markup=get_sub_keyboard())
        return

    try:
        user_data = supabase.table("users").select("*").eq("telegram_id", user_id).execute()
        
        if user_data.data:
            db_user = user_data.data[0]
            link = db_user.get("invite_link")
            count = db_user.get("referred_count", 0)
            
            if not link:
                invite_link_obj = await bot.create_chat_invite_link(
                    chat_id=CHANNEL_USERNAME,
                    name=f"User ID: {user_id}",
                    member_limit=None,
                    expire_date=None
                )
                link = invite_link_obj.invite_link
                supabase.table("users").update({"invite_link": link}).eq("telegram_id", user_id).execute()

            await message.answer(
                f"🔗 **Sizning maxsus taklif havolangiz:**\n{link}\n\n"
                f"Shu havola orqali do'stlaringizni kanalimizga taklif qiling! "
                f"Agar do'stingiz kanalga kirsa **+1**, chiqsa **-1** bo'ladi.\n\n"
                f"📊 **Sizning natijangiz:** {count} ta do'st."
            )
    except Exception as e:
        await message.answer("⚠️ Havola bilan ishlashda xatolik yuz berdi. Bot kanalda admin ekanligini tekshiring.")
        print(f"❌ Taklif xatoligi: {e}")


# --- KANAL HARAKATLARINI KUZATISH ---
@dp.chat_member()
async def on_user_join_or_left(event: ChatMemberUpdated):
    invite_link_used = event.invite_link

    if event.old_chat_member.status in ["left", "kicked", "left_chat_member"] and event.new_chat_member.status in ["member", "administrator"]:
        if invite_link_used:
            try:
                used_link_url = invite_link_used.invite_link
                inviter_check = supabase.table("users").select("*").eq("invite_link", used_link_url).execute()
                
                if inviter_check.data:
                    inviter = inviter_check.data[0]
                    inviter_tg_id = inviter["telegram_id"]
                    new_count = inviter["referred_count"] + 1
                    supabase.table("users").update({"referred_count": new_count}).eq("telegram_id", inviter_tg_id).execute()
                    try:
                        await bot.send_message(chat_id=inviter_tg_id, text=f"🎉 {event.new_chat_member.user.full_name} havolangiz orqali kanalga qo'shildi!\n📊 Jami takliflaringiz: {new_count} ta.")
                    except Exception: pass
            except Exception as e: print(f"❌ A'zo qo'shishda xatolik: {e}")

    elif event.old_chat_member.status in ["member", "administrator"] and event.new_chat_member.status in ["left", "kicked", "left_chat_member"]:
        if invite_link_used and invite_link_used.name and "User ID:" in invite_link_used.name:
            try:
                inviter_tg_id = int(invite_link_used.name.split(":")[1].strip())
                inviter_check = supabase.table("users").select("*").eq("telegram_id", inviter_tg_id).execute()
                if inviter_check.data:
                    inviter = inviter_check.data[0]
                    new_count = max(0, inviter["referred_count"] - 1)
                    supabase.table("users").update({"referred_count": new_count}).eq("telegram_id", inviter_tg_id).execute()
                    try:
                        await bot.send_message(chat_id=inviter_tg_id, text=f"📉 Ogohlantirish: Bir do'stingiz kanalni tark etdi.\n📊 Jami takliflaringiz: {new_count} ta.")
                    except Exception: pass
            except Exception as e: print(f"❌ Chiqishni hisoblashda xatolik: {e}")


# --- KINO KO'RISH BO'LIMI ---
@dp.message(F.text == "🎬 Kino ko'rish")
async def choose_quality(message: types.Message):
    if not await check_sub(message.from_user.id):
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'lishingiz shart:", reply_markup=get_sub_keyboard())
        return

    kb = [[InlineKeyboardButton(text="📱 720p (O'rtacha sifat)", callback_data="quality_720p HD"), InlineKeyboardButton(text="🖥️ 1080p (Yuqori sifat)", callback_data="quality_1080p HD")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    await message.answer("Kino tomosha qilish uchun oʻzingizga maʼqul boʻlgan video sifatini tanlang: 👇", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("quality_"))
async def show_movies_by_quality(callback: types.CallbackQuery):
    if not await check_sub(callback.from_user.id):
        await callback.answer("⚠️ Avval kanallarga a'zo bo'ling!", show_alert=True)
        return

    selected_quality = callback.data.split("_")[1]
    await callback.message.edit_text(f"⏳ {selected_quality} sifatidagi Garri Potter qismlari yuklanmoqda...")
    try:
        movies_query = supabase.table("movies").select("*").eq("quality", selected_quality).order("part", desc=False).execute()
        if movies_query.data:
            kb = []
            for movie in movies_query.data:
                kb.append([InlineKeyboardButton(text=movie["title"], callback_data=f"sendmovie_{movie['id']}_{selected_quality}")])
            kb.append([InlineKeyboardButton(text="⬅️ Sifatni qayta tanlash", callback_data="back_to_quality")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
            await callback.message.edit_text(f"🎬 **{selected_quality}** sifatidagi kinolar ro'yxati:\n\nKo'rmoqchi bo'lgan qismingizni tanlang:", reply_markup=keyboard)
        else:
            kb = [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_quality")]]
            keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
            await callback.message.edit_text(f"😔 Afsuski, hozircha bazada {selected_quality} sifatidagi kinolar mavjud emas.", reply_markup=keyboard)
    except Exception as e:
        print(f"❌ Kinolarni olishda xatolik: {e}")
        await callback.message.answer("⚠️ Kinolar ro'yxatini yuklashda texnik xatolik yuz berdi.")

@dp.callback_query(F.data == "back_to_quality")
async def back_to_quality_menu(callback: types.CallbackQuery):
    kb = [[InlineKeyboardButton(text="📱 720p (O'rtacha sifat)", callback_data="quality_720p HD"), InlineKeyboardButton(text="🖥️ 1080p (Yuqori sifat)", callback_data="quality_1080p HD")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    await callback.message.edit_text("Kino tomosha qilish uchun oʻzingizga maʼqul boʻlgan video sifatini tanlang: 👇", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("sendmovie_"))
async def send_movie_to_user(callback: types.CallbackQuery):
    if not await check_sub(callback.from_user.id):
        await callback.answer("⚠️ Avval kanallarga a'zo bo'ling!", show_alert=True)
        return

    data_parts = callback.data.split("_")
    movie_id = data_parts[1]
    current_quality = data_parts[2] if len(data_parts) > 2 else "720p HD"
    
    await callback.answer("⏳ Kino tayyorlanmoqda...")
    try:
        movie_data = supabase.table("movies").select("*").eq("id", movie_id).execute()
        if movie_data.data:
            movie = movie_data.data[0]
            
            back_kb = [[InlineKeyboardButton(text="⬅️ Kinolar ro'yxatiga qaytish", callback_data=f"quality_{current_quality}")]]
            back_markup = InlineKeyboardMarkup(inline_keyboard=back_kb)
            
            await callback.message.answer_video(
                video=movie["file_id"], 
                caption=f"🎬 **{movie['title']}**\n\n⚙️ Sifati: {movie['quality']}\n\n✨ Yoqimli tomosha tilaymiz! ⚡",
                reply_markup=back_markup
            )
        else:
            await callback.message.answer("⚠️ Kechirasiz, ushbu kino bazadan topilmadi.")
    except Exception as e:
        print(f"❌ KINONI FOYDALANUVCHIGA YUBORISHDA XATOLIK: {e}")
        await callback.message.answer(f"❌ Kinoni yuborishda texnik xatolik yuz berdi.\n\nSababi: {e}")


# --- KITOB O'QISH BO'LIMI ---
@dp.message(F.text == "📚 Kitob o'qish")
async def show_books(message: types.Message):
    if not await check_sub(message.from_user.id):
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'lishingiz shart:", reply_markup=get_sub_keyboard())
        return

    await message.answer("⏳ Garri Potter kitoblari ro'yxati yuklanmoqda...")
    await list_books_interface(message, is_edit=False)

async def list_books_interface(message_obj, is_edit=False):
    try:
        books_query = supabase.table("books").select("*").execute()
        if books_query.data:
            kb = []
            for book in books_query.data:
                kb.append([InlineKeyboardButton(text=f"📘 {book['title']}", callback_data=f"sendbook_{book['id']}")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
            
            text = "📚 **Garri Potter olamiga oid kitoblar:**\n\nO'qimoqchi bo'lgan kitobingizni tanlang:"
            if is_edit:
                await message_obj.edit_text(text, reply_markup=keyboard)
            else:
                await message_obj.answer(text, reply_markup=keyboard)
        else:
            if is_edit:
                await message_obj.edit_text("😔 Hozircha kutubxonaga kitoblar joylanmagan.")
            else:
                await message_obj.answer("😔 Hozircha kutubxonaga kitoblar joylanmagan.")
    except Exception as e:
        print(f"❌ Kitoblarni yuklashda xatolik: {e}")
        if is_edit:
            await message_obj.edit_text("⚠️ Kitoblar ro'yxatini yuklashda texnik xatolik yuz berdi.")
        else:
            await message_obj.answer("⚠️ Kitoblar ro'yxatini yuklashda texnik xatolik yuz berdi.")

@dp.callback_query(F.data.startswith("sendbook_"))
async def send_book_to_user(callback: types.CallbackQuery):
    if not await check_sub(callback.from_user.id):
        await callback.answer("⚠️ Avval kanallarga a'zo bo'ling!", show_alert=True)
        return

    book_id = callback.data.split("_")[1]
    try:
        book_data = supabase.table("books").select("*").eq("id", book_id).execute()
        if book_data.data:
            book = book_data.data[0]
            
            back_kb = [[InlineKeyboardButton(text="⬅️ Kitoblar ro'yxatiga qaytish", callback_data="back_to_books")]]
            back_markup = InlineKeyboardMarkup(inline_keyboard=back_kb)
            
            await callback.message.answer_document(
                document=book["file_id"], 
                caption=f"📘 **{book['title']}**\n\n✨ Sehrli mutolaa tilaymiz! ⚡",
                reply_markup=back_markup
            )
            await callback.answer()
        else:
            await callback.answer("⚠️ Kitob topilmadi!", show_alert=True)
    except Exception as e:
        print(f"❌ Kitobni yuborishda xatolik: {e}")
        await callback.answer("❌ Kitobni yuborib bo'lmadi.", show_alert=True)

@dp.callback_query(F.data == "back_to_books")
async def back_to_books_callback(callback: types.CallbackQuery):
    if not await check_sub(callback.from_user.id):
        await callback.answer("⚠️ Avval kanallarga a'zo bo'ling!", show_alert=True)
        return
    await callback.answer()
    await list_books_interface(callback.message, is_edit=True)


# --- 🔒 ADMIN PANEL BO'LIMI ---
@dp.message(F.text == "🔒 Admin Panel")
async def admin_auth(message: types.Message, state: FSMContext):
    await message.answer("🔑 Admin panel parolini kiriting:")
    await state.set_state(AdminState.waiting_for_password)

@dp.message(AdminState.waiting_for_password)
async def check_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await state.clear()
        await message.answer(
            "🔓 **Admin Panelga Muvaffaqiyatli Kirdingiz!**\n\nKerakli amalni tanlang: 👇", 
            reply_markup=get_admin_inline_keyboard()
        )
    else:
        await state.clear()
        await message.answer("❌ Parol noto'g'ri!", reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "admin_top_10")
async def admin_show_top_10(callback: types.CallbackQuery):
    await callback.answer("📊 Yuklanmoqda...")
    try:
        top_users = supabase.table("users").select("full_name", "referred_count").order("referred_count", desc=True).limit(10).execute()
        text = "📊 **Eng ko'p do'st taklif qilganlar (TOP 10):**\n\n"
        if top_users.data:
            for i, user in enumerate(top_users.data, 1):
                text += f"{i}. {user['full_name']} — **{user['referred_count']}** ta odam\n"
        else:
            text += "Hozircha hech kim odam taklif qilmadi."
        
        kb = [[InlineKeyboardButton(text="⬅️ Admin Panelga qaytish", callback_data="admin_home")]]
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception as e:
        print(f"❌ Admin top 10 yuklash xatoligi: {e}")
        await callback.message.answer("❌ Ma'lumotlarni yuklashda xatolik yuz berdi.")

@dp.callback_query(F.data == "admin_home")
async def back_to_admin_home(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🔓 **Admin Panel Boshqaruv Menyusi**\n\nKerakli amalni tanlang: 👇", 
        reply_markup=get_admin_inline_keyboard()
    )

@dp.callback_query(F.data == "admin_get_file_id")
async def admin_trigger_video_mode(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminState.waiting_for_admin_video)
    await callback.message.edit_text(
        "📥 **Kino ID olish rejimi yoqildi!**\n\nKanalingizdan videoni shu yerga forward qiling.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]])
    )

@dp.callback_query(F.data == "admin_get_book_id")
async def admin_trigger_book_mode(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminState.waiting_for_admin_book)
    await callback.message.edit_text(
        "📥 **Kitob (PDF) ID olish rejimi yoqildi!**\n\nHujjatni (PDF) shu yerga forward qiling.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]])
    )

@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel_mode(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Rejim bekor qilindi.")
    await callback.message.edit_text(
        "🔓 **Admin Panel Boshqaruv Menyusi**\n\nKerakli amalni tanlang: 👇", 
        reply_markup=get_admin_inline_keyboard()
    )

@dp.message(AdminState.waiting_for_admin_video, F.video)
async def process_admin_video(message: types.Message, state: FSMContext):
    video_file_id = message.video.file_id
    await message.answer(
        f"✅ **Kino ID muvaffaqiyatli olindi!**\n\nKino ID:\n\n`{video_file_id}`",
        parse_mode="Markdown",
        reply_markup=get_admin_inline_keyboard()
    )
    await state.clear()

@dp.message(AdminState.waiting_for_admin_book, F.document)
async def process_admin_book(message: types.Message, state: FSMContext):
    document_file_id = message.document.file_id
    await message.answer(
        f"✅ **Kitob (PDF) ID muvaffaqiyatli olindi!**\n\nKitob ID:\n\n`{document_file_id}`",
        parse_mode="Markdown",
        reply_markup=get_admin_inline_keyboard()
    )
    await state.clear()


# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    print("Garri Potter boti muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot, allowed_updates=["message", "chat_member", "my_chat_member", "callback_query"], handle_signals=False)

if __name__ == "__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): print("Bot to'xtatildi.")