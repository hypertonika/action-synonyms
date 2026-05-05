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


TEACHER_SECTION_TEXT = """<b>Для преподавателя</b>

<b>Цель использования бота</b>
Повышение лексической и цифровой компетенций студентов технических специальностей через интерактивную работу с профессиональной английской лексикой.

<b>Как встроить бот в урок</b>
1. Используйте бот как интерактивный словарь и тренажер по темам профессионального цикла.
2. Включайте квизы, flashcards, Reading и Listening на этапах закрепления, рефлексии и самопроверки.
3. Организуйте парную или групповую работу: студенты подбирают синонимы, объясняют термины и составляют мини-диалоги.
4. Сочетайте бот с презентациями, Kahoot, LearningApps, Jamboard и другими цифровыми инструментами.

<b>Самостоятельная работа</b>
- Подготовка к тестам, зачетам, проектам и презентациям.
- Задание-пример: пройти 2 квиза по теме и использовать 5 новых слов в мини-диалоге.
- Тренировка перевода терминов, подбора синонимов и повторения тематической лексики.

<b>Критерии оценивания</b>
1. Профессиональная лексика: понимание и корректное употребление слов и синонимов - 0-3 балла.
2. Активность: участие в квизах, flashcards и тестах - 0-3 балла.
3. Самостоятельность: работа с ботом вне занятий - 0-2 балла.
4. Цифровая грамотность: уверенная работа с Telegram-ботом и онлайн-платформами - 0-2 балла.
5. Результативность: средний процент правильных ответов выше 70% - 0-2 балла.

<b>Итоговая шкала</b>
10-12 баллов - высокий уровень.
7-9 баллов - средний уровень.
до 6 баллов - начальный уровень.

<b>Методические рекомендации</b>
- Бот можно использовать как основное средство изучения лексики или как дополнительный цифровой ресурс.
- Лучше сочетать его с работой с текстом, устной практикой и письменными заданиями.
- После работы с ботом полезно провести рефлексию: новые слова, трудности, примеры употребления.
- Для мини-проектов можно дать задание: Create a presentation using 10 synonyms from the Mining topic.

<b>Часто задаваемые вопросы</b>
<b>Вопрос:</b> Можно ли использовать бот, если в группе студенты с разным уровнем английского?
<b>Ответ:</b> Да. Бот содержит лексику уровня A2-B1. Можно давать разные задания: слабым студентам - перевод и простые тесты, сильным - подбор синонимов в контексте и эссе.

<b>Вопрос:</b> Как отследить прогресс студентов, если бот не сохраняет историю?
<b>Ответ:</b> Поощряйте студентов делать скриншоты результатов тестов и отправлять вам. Также можно использовать Google Forms для фиксации баллов.

<b>Вопрос:</b> Нужно ли специальное обучение для работы с ботом?
<b>Ответ:</b> Нет, интерфейс интуитивно понятен. Достаточно один раз показать студентам, как найти модули и запустить тест.

Полный список литературы и источников доступен в разделе <b>О боте</b>."""


ABOUT_BOT_TEXT = """<b>О боте</b>

Telegram-бот предназначен для изучения английской лексики, синонимов и профессиональных терминов технического и горного направлений. Он помогает работать со словарем, квизами, карточками, Reading и Listening-заданиями.

<b>Источники и литература</b>
1. Jenny Dooley, Bob Obee. <i>Action for Kazakhstan. Grade 11. Student's Book</i>. Express Publishing, 2020.
2. Полякова Т.Ю., Синявская Е.В., Тынкова О.И., Улановская Э.С. <i>Английский язык для инженеров</i>. 6-е изд., испр. М.: Высшая школа, 2003. 463 с.
3. Литвинов П.П. <i>Англо-русский и русско-английский синонимический словарь с тематической классификацией. Продвинутый английский через синонимию</i>. М.: Яхонт-А, 2002. 384 с. ISBN 5-901860-20-9.
4. <i>Webster's Dictionary of Synonyms</i>. Springfield, Mass., 1951; 2nd ed., 1968.
5. Агабекян И.П. <i>Английский язык для ССУЗов</i>. Москва, 2012.
6. Хохряков В.С. <i>Открытая разработка месторождений полезных ископаемых</i>.
7. Гарагуля С.И. <i>Английский язык для студентов строительных специальностей. Learning Building Construction in English</i>. Ростов н/Д: Феникс, 2011. 347 с.
8. Ш. Әбдіраман. <i>Кенісі технологиясының негіздері</i>.
9. Ә. Байбатина. <i>Пайдалы қазбалар</i>.
10. Бонами Д. <i>Английский язык для технических училищ</i>. Предисл. В.Б. Григорова. М.: Высшая школа, 1989. 287 с.
11. <i>Горное дело: Основные способы добычи угля и современное оборудование</i>. Пособие по английскому языку. Кемерово, 2009.
12. Литвинов П.П. <i>Англо-русский и русско-английский синонимический словарь с тематической классификацией</i>. М.: Яхонт-А, 2002. 384 с."""


# FSM для квиза
TEACHER_MENU_TEXT = """<b>Методический раздел</b>

Материалы для планирования урока, самостоятельной работы и оценки результатов.

Выберите нужный блок:"""


TEACHER_MENU_SECTIONS = {
    "goals": """<b>Цели и задачи</b>

<b>Общая цель</b>
Повышение уровня лексической и цифровой компетенций студентов технических специальностей через интерактивный цифровой ресурс.

<b>Конкретные цели</b>
- формировать профессионально-ориентированный словарный запас;
- развивать понимание английских синонимов, определений и терминов;
- повышать мотивацию к изучению английского языка;
- развивать самостоятельное обучение, самооценку и рефлексию;
- формировать цифровую грамотность.

<b>Задачи</b>
- расширить активный и пассивный словарь студентов;
- создать условия для интерактивного изучения лексики;
- внедрить элементы геймификации: quiz, flashcards, mini-tests;
- развивать командное взаимодействие;
- интегрировать мобильные технологии в обучение.""",
    "lesson": """<b>Интеграция бота в урок</b>

<b>В учебном процессе</b>
1. Используйте бот как интерактивный словарь и тренажер по профессиональным темам.
2. Включайте квизы, подбор синонимов, Reading и Listening на этапах закрепления, рефлексии или самопроверки.
3. Применяйте бот в парной и групповой работе для активизации устной речи.
4. Сочетайте бот с презентациями, Jamboard, Kahoot, LearningApps и другими цифровыми средствами.

<b>В самостоятельной работе</b>
- рекомендуйте бот при подготовке к тестам, зачетам, проектам и презентациям;
- давайте задания формата: "Пройди 2 квиза по теме и используй 5 новых слов в мини-диалоге";
- используйте бот для тренировки перевода терминов, подбора синонимов и повторения тем.""",
    "criteria": """<b>Критерии оценивания</b>

<pre>
1. Профессиональная лексика      0-3
2. Активность в работе с ботом   0-3
3. Самостоятельность             0-2
4. Цифровая грамотность          0-2
5. Результативность              0-2
</pre>

<b>Максимум:</b> 12 баллов.

<b>Интерпретация результатов</b>
10-12 баллов - высокий уровень.
7-9 баллов - средний уровень.
до 6 баллов - начальный уровень.

<b>Показатель результативности</b>
Средний процент правильных ответов выше 70%.""",
    "method": """<b>Методические рекомендации</b>

1. Бот может использоваться как основное средство изучения лексики или как дополнительный цифровой ресурс.
2. Эффективен в рамках компетентностного подхода: студенты учатся применять иностранный язык в профессиональных ситуациях.
3. Использование бота развивает функциональную грамотность, цифровые навыки и языковую самостоятельность.
4. Рекомендуется сочетать бот с традиционными методами: работой с текстом, упражнениями и устной практикой.

<b>Идея мини-проекта</b>
Create a presentation using 10 synonyms from the Mining topic.""",
    "faq": """<b>Часто задаваемые вопросы</b>

<b>Можно ли использовать бот, если в группе студенты с разным уровнем английского?</b>
Да. Бот содержит лексику уровня A2-B1. Слабым студентам можно давать перевод и простые тесты, сильным - подбор синонимов в контексте и эссе.

<b>Как отследить прогресс студентов, если бот не сохраняет историю?</b>
Поощряйте студентов делать скриншоты результатов тестов и отправлять вам. Также можно использовать Google Forms для фиксации баллов.

<b>Нужно ли специальное обучение для работы с ботом?</b>
Нет. Интерфейс интуитивно понятен. Достаточно один раз показать студентам, как найти модули и запустить тест.""",
}


ABOUT_MENU_TEXT = """<b>О боте</b>

Action Synonyms Bot - учебный Telegram-бот для работы с английской лексикой, синонимами и профессиональными терминами технического и горного направлений.

Выберите раздел:"""


ABOUT_MENU_SECTIONS = {
    "purpose": """<b>Назначение</b>

Бот помогает студентам изучать и повторять английскую лексику через словарь, карточки, квизы, Reading и Listening-задания.

<b>Основные возможности</b>
- поиск перевода и синонимов;
- работа с профессиональной терминологией;
- тренировка через flashcards;
- проверка знаний в quiz-формате;
- развитие навыков чтения и аудирования.""",
    "base": """<b>Учебная и методическая база</b>

Содержание бота опирается на учебники английского языка, словари синонимов и литературу по техническим и горным специальностям.

<b>Направления материалов</b>
- общий английский и школьный курс Grade 11;
- английский язык для инженеров и студентов технических специальностей;
- синонимия и тематическая классификация лексики;
- терминология горного дела, строительства и полезных ископаемых.""",
    "sources": """<b>Источники и литература</b>

1. Jenny Dooley, Bob Obee. <i>Action for Kazakhstan. Grade 11. Student's Book</i>. Express Publishing, 2020.
2. Полякова Т.Ю., Синявская Е.В., Тынкова О.И., Улановская Э.С. <i>Английский язык для инженеров</i>. М.: Высшая школа, 2003.
3. Литвинов П.П. <i>Англо-русский и русско-английский синонимический словарь с тематической классификацией</i>. М.: Яхонт-А, 2002.
4. <i>Webster's Dictionary of Synonyms</i>. Springfield, Mass., 1951; 2nd ed., 1968.
5. Агабекян И.П. <i>Английский язык для ССУЗов</i>. Москва, 2012.
6. Хохряков В.С. <i>Открытая разработка месторождений полезных ископаемых</i>.
7. Гарагуля С.И. <i>Learning Building Construction in English</i>. Ростов н/Д: Феникс, 2011.
8. Ш. Әбдіраман. <i>Кенісі технологиясының негіздері</i>.
9. Ә. Байбатина. <i>Пайдалы қазбалар</i>.
10. Бонами Д. <i>Английский язык для технических училищ</i>. М.: Высшая школа, 1989.
11. <i>Горное дело: Основные способы добычи угля и современное оборудование</i>. Кемерово, 2009.
12. Литвинов П.П. <i>Англо-русский и русско-английский синонимический словарь с тематической классификацией</i>. М.: Яхонт-А, 2002.""",
}


def teacher_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Цели и задачи", callback_data="teacher:goals")],
        [InlineKeyboardButton(text="📚 Интеграция в урок", callback_data="teacher:lesson")],
        [InlineKeyboardButton(text="🧾 Критерии оценивания", callback_data="teacher:criteria")],
        [InlineKeyboardButton(text="🧭 Методические рекомендации", callback_data="teacher:method")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="teacher:faq")],
    ])


def teacher_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к разделам", callback_data="teacher:menu")]
    ])


def about_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ Назначение", callback_data="about:purpose")],
        [InlineKeyboardButton(text="📘 Учебная база", callback_data="about:base")],
        [InlineKeyboardButton(text="📚 Источники и литература", callback_data="about:sources")],
    ])


def about_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к разделам", callback_data="about:menu")]
    ])


TEACHER_CARD_TITLES = {
    "goals": "🎯 Цели и задачи",
    "lesson": "📚 Интеграция в урок",
    "criteria": "🧾 Критерии оценивания",
    "method": "🧭 Методические рекомендации",
    "faq": "❓ FAQ",
}


ABOUT_CARD_TITLES = {
    "purpose": "ℹ️ Назначение",
    "base": "📘 Учебная база",
    "sources": "📚 Источники и литература",
}


def context_text(section_group: str, section_title: str, body: str) -> str:
    body = re.sub(r"^<b>[^<]+</b>\n\n", "", body, count=1)
    return (
        f"{section_group} → {section_title}\n\n"
        f"{body}"
    )


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
        "6. Используйте `/reading`, чтобы открыть раздел чтения: словарь по теме, текст, обсуждение и квиз.\n"
        "   — Внутри раздела навигируйте кнопками *Назад* и *Далее*;\n"
        "   — В заданиях отправляйте ответы прямо сообщением;\n"
        "   — Результаты квиза показываются во всплывающем окне.\n"
        "7. Используйте `/listening`, чтобы пройти уроки аудирования: прослушивание аудио, вопросы и задание fill-in-the-gaps.\n"
        "   — Аудио отправляется как голосовое сообщение;\n"
        "   — В fill-in-the-gaps отправляйте слова через запятую.\n"
        "8. Администраторы могут добавлять новые слова с помощью команды `/add_word`.\n\n"
        "💡 В любой момент введите 'отмена', чтобы прервать текущую операцию.\n\n"
        "👨‍🏫 *Команды:*\n"
        "🔹 `/start` — начать работу с ботом\n"
        "🔹 `/list` — список слов по буквам\n"
        "🔹 `/help` — описание функциональности\n"
        "🔹 `/add_word` — добавить слово (только для админов)\n"
        "🔹 `/random_word` — получить случайное слово\n"
        "🔹 `/flashcards` — режим обучения по карточкам\n"
        "🔹 `/start_quiz` — начать викторину\n"
        "🔹 `/reading` — открыть уроки чтения\n"
        "🔹 `/listening` — открыть уроки аудирования\n",
        parse_mode="Markdown",
    )


# FSM для добавления нового слова
@router.message(Command("teacher"))
@router.message(F.text == "Для преподавателя")
async def teacher_section(message: Message):
    await message.answer(
        TEACHER_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=teacher_menu_keyboard(),
    )


@router.message(Command("about"))
@router.message(F.text == "О боте")
async def about_bot(message: Message):
    await message.answer(
        ABOUT_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=about_menu_keyboard(),
    )


@router.callback_query(F.data == "teacher:menu")
async def teacher_menu(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        TEACHER_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=teacher_menu_keyboard(),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("teacher:"))
async def teacher_menu_section(callback_query: CallbackQuery):
    section = callback_query.data.split(":", 1)[1]
    text = TEACHER_MENU_SECTIONS.get(section)
    if not text:
        await callback_query.answer("Раздел не найден", show_alert=True)
        return

    await callback_query.message.edit_text(
        context_text(
            "👩‍🏫 Методический раздел",
            TEACHER_CARD_TITLES.get(section, "Раздел"),
            text,
        ),
        parse_mode="HTML",
        reply_markup=teacher_back_keyboard(),
    )
    await callback_query.answer()


@router.callback_query(F.data == "about:menu")
async def about_menu(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        ABOUT_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=about_menu_keyboard(),
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("about:"))
async def about_menu_section(callback_query: CallbackQuery):
    section = callback_query.data.split(":", 1)[1]
    text = ABOUT_MENU_SECTIONS.get(section)
    if not text:
        await callback_query.answer("Раздел не найден", show_alert=True)
        return

    await callback_query.message.edit_text(
        context_text(
            "ℹ️ О боте",
            ABOUT_CARD_TITLES.get(section, "Раздел"),
            text,
        ),
        parse_mode="HTML",
        reply_markup=about_back_keyboard(),
    )
    await callback_query.answer()


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
        [InlineKeyboardButton(text="General English", callback_data="cat_dictionary")],
        [InlineKeyboardButton(text="Technical Thesaurus", callback_data="cat_mining")]
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
    builder.button(text="General English", callback_data="list_dictionary")
    builder.button(text="Technical Thesaurus", callback_data="list_mining")
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
        "📚 *General English*\n\nВыберите букву:",
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
        "📚 *Technical Thesaurus*\n\nВыберите букву:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )

@router.callback_query(lambda c: c.data == "back_to_categories")
async def back_to_categories(callback_query: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="General English", callback_data="list_dictionary")
    builder.button(text="Technical Thesaurus", callback_data="list_mining")
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

    
@router.message(F.text)   
async def handle_word(message: Message):
    text = (message.text or "").strip()
    if not text:
        return

    word = text
    # Формируем регулярное выражение для точного совпадения, игнорируя регистр
    regex = f"^{re.escape(word)}$"
    doc = await all_words_col.find_one({"word": {"$regex": regex, "$options": "i"}})

    if doc:
        synonyms = doc.get("synonyms", [])
        ru = doc.get("ru", "")
        kz = doc.get("kz", "")
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

