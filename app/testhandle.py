from aiogram import Router, types, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    CallbackQuery,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from app.keyboards import main
import json
import os
import motor.motor_asyncio
import asyncio
from fuzzywuzzy import process
import random
import re

# MongoDB configuration
MONGO_URI = os.environ.get("MONGO_URI")
DB_NAME = "bot_database"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
dictionary_col = db["dictionary"]
quiz_col = db["quiz_data"]
mining_words_col = db["mining_words"]
mining_quizzes_col = db["mining_quizzes"]
all_words_col = db["all_words"]
admins_col = db["admins"]
router = Router()


# FSM для квиза
class QuizState(StatesGroup):
    waiting_for_answer = State()
    quiz_data = State()
    current_question = State()
    score = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я - бот-словарь. Напиши мне слово на английском, и я переведу его на русский и казахский.\n\n"
        "👨‍🏫 *Доступные команды:*\n"
        "🔹 `/help` - подробная инструкция по использованию бота\n"
        "🔹 `/list` - список слов на выбранную букву\n"
        "🔹 `/add_word` - добавить новое слово (только для админов)\n\n"
        "💡 Введите 'отмена' в любой момент, чтобы прервать операцию.",
        reply_markup=main,
        parse_mode="Markdown",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 *Как пользоваться ботом:*\n\n"
        "1. Отправьте слово на английском, чтобы получить его перевод и синонимы.\n"
        "2. Используйте команду `/list`, чтобы выбрать букву и просмотреть слова.\n"
        "3. Используйте `/random_word`, чтобы получить случайное слово.\n"
        "4. Используйте `/flashcards`, чтобы начать обучение по карточкам.\n"
        "5. Используйте `/start_quiz`, чтобы проверить свои знания с помощью викторины.\n"
        "6. Администраторы могут добавлять новые слова с помощью команды `/add_word`.\n\n"
        "💡 В любой момент введите 'отмена', чтобы прервать текущую операцию.\n\n"
        "👨‍🏫 *Команды:*\n"
        "🔹 `/start` - начать работу с ботом\n"
        "🔹 `/list` - список слов по буквам\n"
        "🔹 `/help` - описание функциональности\n"
        "🔹 `/add_word` - добавить слово (только для админов)\n"
        "🔹 `/random_word` - получить случайное слово\n"
        "🔹 `/flashcards` - режим обучения по карточкам\n"
        "🔹 `/start_quiz` - начать викторину",
        parse_mode="Markdown",
    )


# FSM для добавления нового слова
class AddWord(StatesGroup):
    waiting_for_category = State()  
    waiting_for_word = State()
    waiting_for_synonyms = State()
    waiting_for_ru_translation = State()
    waiting_for_kz_translation = State()
    confirmation = State()


def confirmation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_addition")
    builder.button(text="❌ Отмена", callback_data="cancel_addition")
    return builder.as_markup()


def cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_addition")
    return builder.as_markup()


@router.message(Command("add_word"))
async def start_add_word(message: Message, state: FSMContext):
    # Проверяем права администратора через коллекцию admins_col
    admin_doc = await admins_col.find_one({"admin_id": message.from_user.id})
    if not admin_doc:
        await message.answer("У вас нет прав для добавления новых слов.")
        return

    # Запрашиваем выбор категории
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Action Synonyms", callback_data="cat_dictionary")],
        [InlineKeyboardButton(text="Technical Mining Thesaurus", callback_data="cat_mining")]
    ])
    await message.answer("Выберите категорию для добавления слова:", reply_markup=keyboard)
    await state.set_state(AddWord.waiting_for_category)


@router.callback_query(lambda c: c.data in ["cat_dictionary", "cat_mining"])
async def choose_category(callback_query: CallbackQuery, state: FSMContext):
    category = callback_query.data  # "cat_dictionary" или "cat_mining"
    await state.update_data(category=category)
    await callback_query.message.edit_text("Введите слово на английском:", reply_markup=cancel_keyboard())
    await state.set_state(AddWord.waiting_for_word)


@router.message(AddWord.waiting_for_word)
async def get_english_word(message: Message, state: FSMContext):
    await state.update_data(word=message.text.strip().capitalize())
    await message.answer("Введите синонимы через запятую:", reply_markup=cancel_keyboard())
    await state.set_state(AddWord.waiting_for_synonyms)


@router.message(AddWord.waiting_for_synonyms)
async def get_synonyms(message: Message, state: FSMContext):
    synonyms = [s.strip() for s in message.text.split(",")]
    await state.update_data(synonyms=synonyms)
    await message.answer("Введите русский перевод:", reply_markup=cancel_keyboard())
    await state.set_state(AddWord.waiting_for_ru_translation)


@router.message(AddWord.waiting_for_ru_translation)
async def get_russian_translation(message: Message, state: FSMContext):
    await state.update_data(ru=message.text.strip())
    await message.answer("Введите казахский перевод:", reply_markup=cancel_keyboard())
    await state.set_state(AddWord.waiting_for_kz_translation)


@router.message(AddWord.waiting_for_kz_translation)
async def get_kazakh_translation(message: Message, state: FSMContext):
    await state.update_data(kz=message.text.strip())
    data = await state.get_data()
    word_info = (
        f"🔹 **Слово**: {data['word']}\n"
        f"🔹 **Синонимы**: {', '.join(data['synonyms'])}\n"
        f"🔹 **Русский перевод**: {data['ru']}\n"
        f"🔹 **Казахский перевод**: {data['kz']}"
    )
    await message.answer(
        f"Проверьте данные перед добавлением:\n\n{word_info}",
        parse_mode="Markdown",
        reply_markup=confirmation_keyboard(),
    )
    await state.set_state(AddWord.confirmation)


@router.callback_query(F.data == "cancel_addition")
async def cancel_addition(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("❌ Операция отменена.")
    await state.clear()


@router.callback_query(F.data == "confirm_addition")
async def confirm_addition(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    word = data["word"]
    synonyms = data["synonyms"]
    ru = data["ru"]
    kz = data["kz"]
    category = data.get("category")

    # Добавляем в соответствующую коллекцию по категории
    if category == "cat_dictionary":
        await dictionary_col.update_one(
            {"word": word},
            {"$set": {"synonyms": synonyms, "ru": ru, "kz": kz}},
            upsert=True,
        )
    elif category == "cat_mining":
        await mining_words_col.update_one(
            {"word": word},
            {"$set": {"synonyms": synonyms, "ru": ru, "kz": kz}},
            upsert=True,
        )

    # Обязательно добавляем слово в коллекцию all_words
    await all_words_col.update_one(
        {"word": word},
        {"$set": {"synonyms": synonyms, "ru": ru, "kz": kz}},
        upsert=True,
    )

    await callback_query.message.edit_text("✅ Слово успешно добавлено!")
    await state.clear()


# ===== Изменения для команды /list =====
@router.message(Command("list"))
async def cmd_list(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="Action Synonyms", callback_data="list_dictionary")
    builder.button(text="Technical Mining Thesaurus", callback_data="list_mining")
    keyboard = builder.as_markup()
    await message.answer("📚 Выберите категорию:", reply_markup=keyboard)


def generate_alphabet_keyboard_for_collection(prefix: str):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    builder = InlineKeyboardBuilder()
    for letter in alphabet:
        builder.button(text=letter, callback_data=f"{prefix}{letter}")
    builder.adjust(6)
    return builder.as_markup()


@router.callback_query(lambda c: c.data == "list_dictionary")
async def list_dictionary_handler(callback_query: CallbackQuery):
    keyboard = generate_alphabet_keyboard_for_collection("letter_")
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_categories")
    ])
    await callback_query.message.edit_text(
        "📚 *Action Synonyms*\n\nВыберите букву:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )



@router.callback_query(lambda c: c.data == "list_mining")
async def list_mining_handler(callback_query: CallbackQuery):
    keyboard = generate_alphabet_keyboard_for_collection("mining_letter_")
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Назад ↩️", callback_data="back_to_categories")
    ])
    await callback_query.message.edit_text(
        "📚 *Technical Mining Thesaurus*\n\nВыберите букву:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )

@router.callback_query(lambda c: c.data == "back_to_categories")
async def back_to_categories(callback_query: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="Action Synonyms", callback_data="list_dictionary")
    builder.button(text="Technical Mining Thesaurus", callback_data="list_mining")
    keyboard = builder.as_markup()
    await callback_query.message.edit_text("📚 Выберите категорию:", reply_markup=keyboard)



@router.callback_query(lambda c: c.data and c.data.startswith("letter_"))
async def handle_letter_selection(callback_query: CallbackQuery):
    letter = callback_query.data.split("_")[1]
    cursor = dictionary_col.find({"word": {"$regex": f"^{letter}"}})
    docs = await cursor.to_list(length=None)
    words = sorted([doc["word"] for doc in docs])
    if words:
        response = f"📃 *Слова на букву {letter}:*\n\n" + "\n".join(
            f"🔹 {word}" for word in words
        )
    else:
        response = f"⚠️ На букву {letter} нет слов в словаре."
    await callback_query.message.edit_text(response, parse_mode="Markdown")


@router.callback_query(lambda c: c.data and c.data.startswith("mining_letter_"))
async def handle_mining_letter_selection(callback_query: CallbackQuery):
    parts = callback_query.data.split("_")
    letter = parts[2] if len(parts) > 2 else ""
    cursor = mining_words_col.find({"word": {"$regex": f"^{letter}"}})
    docs = await cursor.to_list(length=None)
    words = sorted([doc["word"] for doc in docs])
    if words:
        response = f"📃 *Слова на букву {letter}:*\n\n" + "\n".join(
            f"🔹 {word}" for word in words
        )
    else:
        response = f"⚠️ На букву {letter} нет слов в техничес майнинговом тезаурусе."
    await callback_query.message.edit_text(response, parse_mode="Markdown")
# ===== Конец изменений для команды /list =====


@router.message(Command("random_word"))
async def cmd_random_word(message: Message):
    # Используем агрегацию для получения случайного документа из коллекции random_words
    docs = await all_words_col.aggregate([{"$sample": {"size": 1}}]).to_list(length=1)
    if not docs:
        await message.answer(
            "⚠️ Словарь пуст. Добавьте слова с помощью команды `/add_word`."
        )
        return

    doc = docs[0]
    word = doc.get("word")
    synonyms = doc.get("synonyms", [])
    ru = doc.get("ru", "Нет перевода")
    kz = doc.get("kz", "Нет перевода")

    response = (
        f"✨ *Случайное слово: {word}*\n\n"
        f"🔹 *Синонимы*: {', '.join(synonyms) if synonyms else 'Нет синонимов'}\n"
        f"🔸 *На русском*: {ru}\n"
        f"🔸 *На казахском*: {kz}"
    )

    await message.answer(response, parse_mode="Markdown")


# FSM для режима карточек
class FlashcardState(StatesGroup):
    viewing = State()


def escape_markdown_v2(text: str) -> str:
    return re.sub(r"([_\*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)


def generate_flashcard(word, synonyms, ru_translation, kz_translation):
    word = escape_markdown_v2(word)
    synonyms = [escape_markdown_v2(syn) for syn in synonyms]
    ru_translation = escape_markdown_v2(ru_translation)
    kz_translation = escape_markdown_v2(kz_translation)

    return (
        f"✨ *{word}*\n\n"
        f"🔹 *Синонимы: *||{', '.join(synonyms)}||\n"
        f"🔸 *На русском: *||{ru_translation}||\n"
        f"🔸 *На казахском: *||{kz_translation}||"
    )


def generate_flashcard_navigation_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Предыдущее слово", callback_data="previous_word"
                ),
                InlineKeyboardButton(text="Следующее слово", callback_data="next_word"),
            ],
            [InlineKeyboardButton(text="Выход", callback_data="exit_flashcards")],
        ]
    )
    return keyboard


@router.message(Command("flashcards"))
async def start_flashcards(message: Message, state: FSMContext):
    user_data = await state.get_data()
    if "message_id" in user_data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id, message_id=user_data["message_id"]
            )
        except Exception:
            pass

    docs = await all_words_col.find({}).to_list(length=None)
    if not docs:
        await message.answer(
            "⚠️ Словарь пуст. Добавьте слова с помощью команды `/add_word`."
        )
        return

    words = [doc["word"] for doc in docs]
    random.shuffle(words)
    current_index = 0
    await state.update_data(words=words, current_index=current_index)

    doc = await all_words_col.find_one({"word": words[current_index]})
    response = generate_flashcard(
        doc["word"], doc.get("synonyms", []), doc.get("ru", ""), doc.get("kz", "")
    )
    keyboard = generate_flashcard_navigation_keyboard()

    msg = await message.answer(response, reply_markup=keyboard, parse_mode="MarkdownV2")
    await state.update_data(message_id=msg.message_id)
    await state.set_state(FlashcardState.viewing)


@router.callback_query(FlashcardState.viewing, F.data == "next_word")
async def next_word(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_index = user_data["current_index"]
    words = user_data["words"]

    current_index = (current_index + 1) % len(words)
    await state.update_data(current_index=current_index)

    doc = await all_words_col.find_one({"word": words[current_index]})
    response = generate_flashcard(
        doc["word"], doc.get("synonyms", []), doc.get("ru", ""), doc.get("kz", "")
    )
    keyboard = generate_flashcard_navigation_keyboard()

    await callback_query.message.delete()
    msg = await callback_query.message.answer(
        response, reply_markup=keyboard, parse_mode="MarkdownV2"
    )
    await state.update_data(message_id=msg.message_id)


@router.callback_query(FlashcardState.viewing, F.data == "previous_word")
async def previous_word(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_index = user_data["current_index"]
    words = user_data["words"]

    current_index = (current_index - 1) % len(words)
    await state.update_data(current_index=current_index)

    doc = await all_words_col.find_one({"word": words[current_index]})
    response = generate_flashcard(
        doc["word"], doc.get("synonyms", []), doc.get("ru", ""), doc.get("kz", "")
    )
    keyboard = generate_flashcard_navigation_keyboard()

    await callback_query.message.delete()
    msg = await callback_query.message.answer(
        response, reply_markup=keyboard, parse_mode="MarkdownV2"
    )
    await state.update_data(message_id=msg.message_id)


@router.callback_query(FlashcardState.viewing, F.data == "exit_flashcards")
async def exit_flashcards(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Вы вышли из режима карточек.")
    await state.clear()
    await callback_query.message.answer("Выход из режима карточек завершен.")


# Обработчики для квиза (общие тесты)
def generate_options_keyboard(options):
    keyboard = []
    for option in options:
        keyboard.append(
            [InlineKeyboardButton(text=option, callback_data=f"answer_{option[0]}")]
        )
    keyboard.append([InlineKeyboardButton(text="Выход ↩", callback_data="exit_quiz")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def check_quiz_in_progress(state: FSMContext):
    user_data = await state.get_data()
    return "current_question" in user_data


def build_general_quiz_keyboard():
    keyboard = InlineKeyboardBuilder()

    # --- Строка 1: 1..6
    keyboard.row(
        InlineKeyboardButton(text="1", callback_data="quiz_1"),
        InlineKeyboardButton(text="2", callback_data="quiz_2"),
        InlineKeyboardButton(text="3", callback_data="quiz_3"),
        InlineKeyboardButton(text="4", callback_data="quiz_4"),
        InlineKeyboardButton(text="5", callback_data="quiz_5"),
        InlineKeyboardButton(text="6", callback_data="quiz_6"),
    )

    # --- Строка 2: 7..12
    keyboard.row(
        InlineKeyboardButton(text="7", callback_data="quiz_7"),
        InlineKeyboardButton(text="8", callback_data="quiz_8"),
        InlineKeyboardButton(text="9", callback_data="quiz_9"),
        InlineKeyboardButton(text="10", callback_data="quiz_10"),
        InlineKeyboardButton(text="11", callback_data="quiz_11"),
        InlineKeyboardButton(text="12", callback_data="quiz_12"),
    )

    # --- Строка 3: 13..18
    keyboard.row(
        InlineKeyboardButton(text="13", callback_data="quiz_13"),
        InlineKeyboardButton(text="14", callback_data="quiz_14"),
        InlineKeyboardButton(text="15", callback_data="quiz_15"),
        InlineKeyboardButton(text="16", callback_data="quiz_16"),
        InlineKeyboardButton(text="17", callback_data="quiz_17"),
        InlineKeyboardButton(text="18", callback_data="quiz_18"),
    )

    # --- Строка 4: 19..20
    keyboard.row(
        InlineKeyboardButton(text="19", callback_data="quiz_19"),
        InlineKeyboardButton(text="20", callback_data="quiz_20"),
    )

    # --- Строка 5: кнопка «Перейти…»
    keyboard.row(
        InlineKeyboardButton(
            text="Перейти к тематическим тестам (На английском) ➡️",
            callback_data="switch_to_mining_quizzes",
        )
    )

    return keyboard


@router.message(Command("start_quiz"))
async def choose_quiz(message: Message, state: FSMContext):
    if await check_quiz_in_progress(state):
        await message.answer(
            "❌ Вы не можете начать новый квиз, пока не завершите текущий."
        )
        return

    # Вызываем функцию, возвращающую готовую клавиатуру
    keyboard = build_general_quiz_keyboard()
    await message.answer("Выберите раздел:", reply_markup=keyboard.as_markup())


@router.callback_query(lambda c: c.data == "switch_to_mining_quizzes")
async def switch_to_mining_quizzes(callback_query: CallbackQuery):
    # Явно сортируем документы по _id (если хотим в порядке вставки)
    cursor = mining_quizzes_col.find({}).sort("_id", 1)
    docs = await cursor.to_list(length=None)

    unique_sections = []
    seen = set()
    # Собираем разделы в том порядке, в каком документы идут в базе
    for doc in docs:
        section = doc["section"]
        if section not in seen:
            unique_sections.append(section)
            seen.add(section)

    keyboard = InlineKeyboardBuilder()
    # Каждая кнопка в отдельном ряду (полный рост)
    for section in unique_sections:
        keyboard.button(text=section, callback_data=f"mining_quiz::{section}")
    keyboard.adjust(1)

    keyboard.row()
    keyboard.button(
        text="Назад к общим тестам ↩️", callback_data="switch_to_general_quizzes"
    )
    keyboard.adjust(1)

    await callback_query.message.edit_text(
        "Выберите раздел тематических тестов:", reply_markup=keyboard.as_markup()
    )


# Обработчик для возврата к общим тестам
@router.callback_query(lambda c: c.data == "switch_to_general_quizzes")
async def switch_to_general_quizzes(callback_query: CallbackQuery):
    # Повторяем ту же функцию, чтобы раскладка была идентичной
    keyboard = build_general_quiz_keyboard()
    await callback_query.message.edit_text(
        "Выберите раздел:", reply_markup=keyboard.as_markup()
    )


# Обработчик для запуска тематического квиза
@router.callback_query(lambda c: c.data and c.data.startswith("mining_quiz::"))
async def start_mining_quiz(callback_query: CallbackQuery, state: FSMContext):
    section = callback_query.data.split("::")[1]
    doc = await mining_quizzes_col.find_one({"section": section})
    if not doc:
        await callback_query.message.edit_text("❌ Файл с вопросами не найден.")
        return

    quiz_data = doc.get("questions", [])
    await state.update_data(quiz_data=quiz_data, current_question=0, score=0)
    first_question = quiz_data[0]
    keyboard = generate_options_keyboard(first_question["options"])
    await callback_query.message.edit_text(
        f"Вопрос 1: {first_question['question']}", reply_markup=keyboard
    )
    await state.set_state(QuizState.waiting_for_answer)


# Обработчик для общих тестов (старый вариант)
@router.callback_query(lambda c: c.data.startswith("quiz_"))
async def start_selected_quiz(callback_query: CallbackQuery, state: FSMContext):
    if await check_quiz_in_progress(state):
        await callback_query.message.edit_text(
            "❌ Вы не можете начать новый квиз, пока не завершите текущий."
        )
        return

    section_number = callback_query.data.split("_")[1]
    try:
        section = int(section_number)
    except ValueError:
        await callback_query.message.edit_text("❌ Неверный номер раздела.")
        return

    doc = await quiz_col.find_one({"section": section})
    if not doc:
        await callback_query.message.edit_text("❌ Файл с вопросами не найден.")
        return

    quiz_data = doc.get("questions", [])
    await state.update_data(quiz_data=quiz_data, current_question=0, score=0)
    first_question = quiz_data[0]
    keyboard = generate_options_keyboard(first_question["options"])
    await callback_query.message.edit_text(
        f"Вопрос 1: {first_question['question']}", reply_markup=keyboard
    )
    await state.set_state(QuizState.waiting_for_answer)


@router.callback_query(lambda c: c.data.startswith("answer_"))
async def handle_quiz_answer(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_question = user_data["current_question"]
    quiz_data = user_data["quiz_data"]
    score = user_data["score"]

    user_answer = callback_query.data.split("_")[1]
    correct_answer = quiz_data[current_question]["correct_answer"][0]

    if user_answer == correct_answer:
        score += 1
        result_text = "✅ Правильно!"
    else:
        result_text = f"❌ Неправильно! Правильный ответ: {quiz_data[current_question]['correct_answer']}"

    current_question += 1

    if current_question < len(quiz_data):
        next_question = quiz_data[current_question]
        keyboard = generate_options_keyboard(next_question["options"])
        await callback_query.message.edit_text(
            f"{result_text}\n\nВопрос {current_question + 1}: {next_question['question']}",
            reply_markup=keyboard,
        )
        await state.update_data(current_question=current_question, score=score)
    else:
        await callback_query.message.edit_text(
            f"{result_text}\n\nВикторина завершена! Ваш результат: {score}/{len(quiz_data)}"
        )
        await state.clear()


@router.callback_query(lambda c: c.data == "exit_quiz")
async def exit_quiz(callback_query: CallbackQuery, state: FSMContext):
    if await check_quiz_in_progress(state):
        await callback_query.message.edit_text("Операция отменена.")
        await state.clear()
    else:
        await callback_query.message.edit_text(
            "❌ Квиз не активен, нет операции для отмены."
        )

@router.message(F.audio)
async def debug_audio_id(message: Message):
    audio = message.audio
    print("AUDIO file_id:", audio.file_id)
    await message.answer(
        f"🎧 audio.file_id:\n<code>{audio.file_id}</code>",
        parse_mode="HTML"
    )

@router.message(F.voice)
async def debug_voice_id(message: Message):
    voice = message.voice
    print("VOICE file_id:", voice.file_id)
    await message.answer(
        f"🎙 voice.file_id:\n<code>{voice.file_id}</code>",
        parse_mode="HTML"
    )
    
@router.message()
async def handle_word(message: Message):
    # Берем исходное слово без изменения регистра
    word = message.text.strip()
    # Формируем регулярное выражение для точного совпадения, игнорируя регистр
    regex = f"^{re.escape(word)}$"
    doc = await all_words_col.find_one({"word": {"$regex": regex, "$options": "i"}})

    if doc:
        synonyms = doc.get("synonyms", [])
        ru = doc.get("ru", "")
        kz = doc.get("kz", "")
        # Используем значение из базы, чтобы сохранить оригинальное форматирование
        response = (
            f"✨ *{doc['word']}*\n\n"
            f"🔹 *Синонимы*: {', '.join(synonyms)}\n"
            f"🔸 *На русском*: {ru}\n"
            f"🔸 *На казахском*: {kz}"
        )
    else:
        words_list = await all_words_col.distinct("word")
        closest_matches = process.extract(word, words_list, limit=3)
        suggestions = "\n".join([f"🔹 {match[0]}" for match in closest_matches])
        response = (
            f"⚠️ Слово *{word}* не найдено в словаре.\n\n"
            f"Возможно, вы имели в виду:\n{suggestions}\n\n"
            f"Попробуйте ввести другое слово или проверьте правильность написания."
        )

    await message.answer(response, parse_mode="Markdown")
