from aiogram import Router, types, F
from aiogram.types import Message, InlineKeyboardMarkup, CallbackQuery, ReplyKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from app.keyboards import main
import json
import os
from fuzzywuzzy import process
import random
import re
import logging
# Подключаем словарь из JSON файла
def load_dictionary():
    with open("data.json", "r", encoding="utf-8") as file:
        return json.load(file)

# Загружаем словарь
dictionary = load_dictionary()

# Администраторы
ADMINS = [549021481]  # Замените на ваши ID

# Инициализация FSM
class AddWord(StatesGroup):
    waiting_for_word = State()
    waiting_for_synonyms = State()
    waiting_for_ru_translation = State()
    waiting_for_kz_translation = State()
    confirmation = State()

class QuizState(StatesGroup):
    waiting_for_answer = State()
    quiz_data = State()
    current_question = State()
    score = State()

# Состояния для режима карточек
class FlashcardState(StatesGroup):
    viewing = State()


# Пути
JSON_FILE = "data.json"

router = Router()

# Загрузка данных квиза из файла
def load_quiz_data(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)

# Генерация кнопок для выбора ответа
def generate_options_keyboard(options):
    keyboard = []
    for option in options:
        keyboard.append([InlineKeyboardButton(text=option, callback_data=f"answer_{option[0]}")])
    keyboard.append([InlineKeyboardButton(text="Выход ↩", callback_data="exit_quiz")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Проверка, находится ли пользователь в процессе квиза
async def check_quiz_in_progress(state: FSMContext):
    user_data = await state.get_data()
    if "current_question" in user_data:  # Если квиз еще не завершен
        return True
    return False

# Старт квиза
@router.message(Command("start_quiz"))
async def choose_quiz(message: Message, state: FSMContext):
    if await check_quiz_in_progress(state):
        await message.answer("❌ Вы не можете начать новый квиз, пока не завершите текущий.")
        return
    
    keyboard = InlineKeyboardBuilder()
    for i in range(1, 21):
        keyboard.button(text=f"{i}", callback_data=f"quiz_{i}")
    await message.answer("Выберите раздел:", reply_markup=keyboard.as_markup())

# Обработчик других команд
@router.message()
async def handle_other_commands(message: Message, state: FSMContext):
    if await check_quiz_in_progress(state):
        await message.answer("❌ Вы не можете использовать другие команды, пока не завершите текущий квиз.")
        return
    
# Обработчик выбора квиза
@router.callback_query(lambda c: c.data.startswith("quiz_"))
async def start_selected_quiz(callback_query: CallbackQuery, state: FSMContext):
    if await check_quiz_in_progress(state):
        await callback_query.message.edit_text("❌ Вы не можете начать новый квиз, пока не завершите текущий.")
        return
    
    section_number = callback_query.data.split("_")[1]
    filename = f"quiz_data{section_number}.json"
    
    if not os.path.exists(filename):
        await callback_query.message.edit_text("❌ Файл с вопросами не найден.")
        return
    
    # Проверка, что квиз не был уже начат
    user_data = await state.get_data()
    if "current_question" in user_data:
        await callback_query.message.edit_text("❌ Вы уже находитесь в процессе квиза. Завершите текущий, чтобы начать новый.")
        return

    quiz_data = load_quiz_data(filename)
    await state.update_data(quiz_data=quiz_data, current_question=0, score=0)
    
    first_question = quiz_data[0]
    keyboard = generate_options_keyboard(first_question["options"])
    await callback_query.message.edit_text(
        f"Вопрос 1: {first_question['question']}", reply_markup=keyboard
    )
    await state.set_state(QuizState.waiting_for_answer)

# Обработчик выбора ответа
@router.callback_query(lambda c: c.data.startswith("answer_"))
async def handle_quiz_answer(callback_query: CallbackQuery, state: FSMContext):
    if await check_quiz_in_progress(state):
        # Обработка ответа на вопрос
        user_data = await state.get_data()
        current_question = user_data["current_question"]
        quiz_data = user_data["quiz_data"]
        score = user_data["score"]
        
        user_answer = callback_query.data.split("_")[1]  # Получаем выбранный вариант
        correct_answer = quiz_data[current_question]["correct_answer"][0]  # Первая буква правильного ответа
        
        # Формируем ответ
        if user_answer == correct_answer:
            score += 1
            result_text = "✅ Правильно!"
        else:
            result_text = f"❌ Неправильно! Правильный ответ: {quiz_data[current_question]['correct_answer']}"
        
        # Переход к следующему вопросу или завершение викторины
        current_question += 1
        
        if current_question < len(quiz_data):
            next_question = quiz_data[current_question]
            keyboard = generate_options_keyboard(next_question["options"])
            await callback_query.message.edit_text(
                f"{result_text}\n\nВопрос {current_question + 1}: {next_question['question']}",
                reply_markup=keyboard
            )
            await state.update_data(current_question=current_question, score=score)
        else:
            await callback_query.message.edit_text(
                f"{result_text}\n\nВикторина завершена! Ваш результат: {score}/{len(quiz_data)}"
            )
            await state.clear()
    else:
        await callback_query.message.edit_text("❌ Квиз не активен. Используйте команду /start_quiz для начала.")

# Обработчик кнопки "Выход из квиза"
@router.callback_query(lambda c: c.data == "exit_quiz")
async def exit_quiz(callback_query: CallbackQuery, state: FSMContext):
    if await check_quiz_in_progress(state):
        await callback_query.message.edit_text("Операция отменена.")
        await state.clear()  # Очищаем состояние квиза
    else:
        await callback_query.message.edit_text("❌ Квиз не активен, нет операции для отмены.")



def escape_markdown_v2(text: str) -> str:
    # Экранируем специальные символы для MarkdownV2
    return re.sub(r'([_\*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

# Функция для генерации карточки
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

# Функция для создания кнопок навигации
def generate_flashcard_navigation_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Предыдущее слово", callback_data="previous_word"),
                InlineKeyboardButton(text="Следующее слово", callback_data="next_word")
            ],
            [InlineKeyboardButton(text="Выход", callback_data="exit_flashcards")]
        ]
    )
    return keyboard

# Команда для начала режима карточек
@router.message(Command("flashcards"))
async def start_flashcards(message: Message, state: FSMContext):
    # Проверка на существующее состояние карточек
    user_data = await state.get_data()
    if "message_id" in user_data:
        # Удаляем старое сообщение
        await message.bot.delete_message(chat_id=message.chat.id, message_id=user_data["message_id"])

    words = list(dictionary.keys())
    random.shuffle(words)  # Перемешиваем список слов
    current_index = 0
    await state.update_data(words=words, current_index=current_index)

    word = words[current_index]
    details = dictionary[word]
    response = generate_flashcard(word, details["synonyms"], details["ru"], details["kz"])
    keyboard = generate_flashcard_navigation_keyboard()
    
    # Отправляем новое сообщение
    msg = await message.answer(response, reply_markup=keyboard, parse_mode="MarkdownV2")
    await state.update_data(message_id=msg.message_id)  # Сохраняем ID сообщения для удаления в следующий раз
    await state.set_state(FlashcardState.viewing)

# Обработчик для кнопки "Следующее слово"
@router.callback_query(FlashcardState.viewing, F.data == "next_word")
async def next_word(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_index = user_data["current_index"]
    words = user_data["words"]
    
    # Переход к следующему слову
    current_index = (current_index + 1) % len(words)
    await state.update_data(current_index=current_index)

    word = words[current_index]
    details = dictionary[word]
    response = generate_flashcard(word, details["synonyms"], details["ru"], details["kz"])
    keyboard = generate_flashcard_navigation_keyboard()

    # Удаляем старое сообщение и отправляем новое
    await callback_query.message.delete()  # Удаляем старое сообщение
    msg = await callback_query.message.answer(response, reply_markup=keyboard, parse_mode='MarkdownV2')

    # Сохраняем ID нового сообщения для удаления в следующий раз
    await state.update_data(message_id=msg.message_id)

# Обработчик для кнопки "Предыдущее слово"
@router.callback_query(FlashcardState.viewing, F.data == "previous_word")
async def previous_word(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_index = user_data["current_index"]
    words = user_data["words"]
    
    # Переход к предыдущему слову
    current_index = (current_index - 1) % len(words)
    await state.update_data(current_index=current_index)

    word = words[current_index]
    details = dictionary[word]
    response = generate_flashcard(word, details["synonyms"], details["ru"], details["kz"])
    keyboard = generate_flashcard_navigation_keyboard()

    # Удаляем старое сообщение и отправляем новое
    await callback_query.message.delete()  # Удаляем старое сообщение
    msg = await callback_query.message.answer(response, reply_markup=keyboard, parse_mode='MarkdownV2')

    # Сохраняем ID нового сообщения для удаления в следующий раз
    await state.update_data(message_id=msg.message_id)

# Обработчик для кнопки "Выход"
@router.callback_query(FlashcardState.viewing, F.data == "exit_flashcards")
async def exit_flashcards(callback_query: CallbackQuery, state: FSMContext):
    # Очищаем состояние и отправляем сообщение о выходе
    await callback_query.message.edit_text("Вы вышли из режима карточек.")
    await state.clear()  # Очищаем состояние

    # Отправляем сообщение о выходе
    await callback_query.message.answer("Выход из режима карточек завершен.")



def load_data():
    if not os.path.exists(JSON_FILE):
        return {}
    with open(JSON_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

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
async def start_add_word(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await message.answer("У вас нет прав для добавления новых слов.")
        return

    await message.answer("Введите слово на английском:", reply_markup=cancel_keyboard())
    await state.set_state(AddWord.waiting_for_word)

@router.message(AddWord.waiting_for_word)
async def get_english_word(message: types.Message, state: FSMContext):
    await state.update_data(word=message.text.strip())
    await message.answer("Введите синонимы через запятую:", reply_markup=cancel_keyboard())
    await state.set_state(AddWord.waiting_for_synonyms)

@router.message(AddWord.waiting_for_synonyms)
async def get_synonyms(message: types.Message, state: FSMContext):
    synonyms = [s.strip() for s in message.text.split(",")]
    await state.update_data(synonyms=synonyms)
    await message.answer("Введите русский перевод:", reply_markup=cancel_keyboard())
    await state.set_state(AddWord.waiting_for_ru_translation)

@router.message(AddWord.waiting_for_ru_translation)
async def get_russian_translation(message: types.Message, state: FSMContext):
    await state.update_data(ru=message.text.strip())
    await message.answer("Введите казахский перевод:", reply_markup=cancel_keyboard())
    await state.set_state(AddWord.waiting_for_kz_translation)

@router.message(AddWord.waiting_for_kz_translation)
async def get_kazakh_translation(message: types.Message, state: FSMContext):
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
        reply_markup=confirmation_keyboard()
    )
    await state.set_state(AddWord.confirmation)

@router.callback_query(F.data == "cancel_addition")
async def cancel_addition(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("❌ Операция отменена.")
    await state.clear()

@router.callback_query(F.data == "confirm_addition")
async def confirm_addition(callback_query: CallbackQuery, state: FSMContext):
    global dictionary  # Объявляем глобальную переменную для обновления

    data = await state.get_data()
    dictionary = load_data()  # Обновляем данные из файла

    # Добавляем новое слово в словарь
    dictionary[data['word']] = {
        "synonyms": data['synonyms'],
        "ru": data['ru'],
        "kz": data['kz']
    }

    # Сохраняем в файл
    save_data(dictionary)
    
    # Обновляем глобальную переменную словаря
    await callback_query.message.edit_text("✅ Слово успешно добавлено в словарь!")
    await state.clear()

@router.callback_query(F.data == "cancel_addition")
async def cancel_addition(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("❌ Операция отменена.")
    await state.clear()

def generate_alphabet_keyboard():
    # Генерируем кнопки с буквами алфавита
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    builder = InlineKeyboardBuilder()
    for letter in alphabet:
        builder.button(text=letter, callback_data=f"letter_{letter}")
    builder.adjust(6)  # Количество кнопок в строке
    return builder.as_markup()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я - бот-словарь. Напиши мне слово на английском, и я переведу его на русский и казахский.\n\n"
        "👨‍🏫 *Доступные команды:*\n"
        "🔹 `/help` - инструкция по использованию бота\n"
        "🔹 `/list` - список слов на выбранную букву\n"
        "🔹 `/add_word` - добавить новое слово (только для админов)\n\n"
        "💡 Введите 'отмена' в любой момент, чтобы прервать операцию.",
        reply_markup=main,
        parse_mode="Markdown"
    )

@router.message(Command('help'))
async def cmd_help(message: Message):
    await message.answer(
        "📚 *Как пользоваться ботом:*\n\n"
        "1. Отправьте слово на английском, чтобы получить его перевод и синонимы.\n"
        "2. Используйте команду `/list`, чтобы выбрать букву и просмотреть слова.\n"
        "3. Используйте `/random_word`, чтобы получить случайное слово.\n"
        "4. Администраторы могут добавлять новые слова с помощью команды `/add_word`.\n\n"
        "💡 В любой момент введите 'отмена', чтобы прервать текущую операцию.\n\n"
        "👨‍🏫 *Команды:*\n"
        "🔹 `/start` - начать работу с ботом\n"
        "🔹 `/list` - список слов по буквам\n"
        "🔹 `/help` - описание функциональности\n"
        "🔹 `/add_word` - добавить слово (только для админов)\n"
        "🔹 `/random_word` - получить случайное слово",
        parse_mode="Markdown"
    )


@router.message(Command('random_word'))
async def cmd_random_word(message: Message):
    if not dictionary:
        await message.answer("⚠️ Словарь пуст. Добавьте слова с помощью команды `/add_word`.")
        return
    
    word, details = random.choice(list(dictionary.items()))
    synonyms = details.get("synonyms", [])
    ru = details.get("ru", "Нет перевода")
    kz = details.get("kz", "Нет перевода")
    
    response = (
        f"✨ *Случайное слово: {word}*\n\n"
        f"🔹 *Синонимы*: {', '.join(synonyms) if synonyms else 'Нет синонимов'}\n"
        f"🔸 *На русском*: {ru}\n"
        f"🔸 *На казахском*: {kz}"
    )
    
    await message.answer(response, parse_mode="Markdown")

@router.message(Command('list'))
async def cmd_list(message: Message):
    await message.answer(
        "📚 Выберите букву, чтобы увидеть список слов:",
        reply_markup=generate_alphabet_keyboard()
    )

@router.callback_query(lambda c: c.data and c.data.startswith('letter_'))
async def handle_letter_selection(callback_query: CallbackQuery):
    letter = callback_query.data.split('_')[1]  # Получаем выбранную букву
    words = sorted(word for word in dictionary.keys() if word.startswith(letter))
    
    if words:
        response = f"📃 *Слова на букву {letter}:*\n\n" + "\n".join(f"🔹 {word}" for word in words)
    else:
        response = f"⚠️ На букву {letter} нет слов в словаре."
    
    await callback_query.message.edit_text(response, parse_mode="Markdown")

@router.message()
async def handle_word(message: Message):
    word = message.text.strip().capitalize()  # Приводим слово к заглавной букве
    result = dictionary.get(word)
    
    if result:
        synonyms = result.get("synonyms", [])
        ru = result.get("ru", "")
        kz = result.get("kz", "")
        response = (
            f"✨ *{word}*\n\n"
            f"🔹 *Синонимы*: {', '.join(synonyms)}\n"
            f"🔸 *На русском*: {ru}\n"
            f"🔸 *На казахском*: {kz}"
        )
    else:
        # Find closest matches
        closest_matches = process.extract(word, dictionary.keys(), limit=3)
        suggestions = "\n".join([f"🔹 {match[0]}" for match in closest_matches])
        response = (
            f"⚠️ Слово *{word}* не найдено в словаре.\n\n"
            f"Возможно, вы имели в виду:\n{suggestions}\n\n"
            f"Попробуйте ввести другое слово или проверьте правильность написания."
        )
    
    await message.answer(response, parse_mode="Markdown")
