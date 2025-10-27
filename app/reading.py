import io
import re
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, BufferedInputFile
)
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from PIL import Image, ImageDraw, ImageFont

from app.testhandle import db

readings_col = db["readings"]
router_reading = Router()

# ===== FSM =====
class ReadingFlow(StatesGroup):
    choosing_lesson = State()
    in_lesson = State()

class ReadingQuiz(StatesGroup):
    current = State()  # состояние во время локального квиза

STAGES = ["vocab", "text", "discussion", "quiz", "task1", "task2", "task3"]

# ===== UI =====
def nav_kb(stage_idx: int, slug: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    if stage_idx > 0:
        row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"reading:nav:{slug}:{stage_idx-1}"
            )
        )
    if stage_idx < len(STAGES) - 1:
        row.append(
            InlineKeyboardButton(
                text="Далее ➡️",
                callback_data=f"reading:nav:{slug}:{stage_idx+1}"
            )
        )
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text="📚 К списку уроков", callback_data="reading:list")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)

def lessons_kb(lessons):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=r.get("title", "(no title)"),
                callback_data=f"reading:open:{r['slug']}"
            )]
            for r in lessons
        ]
    )

async def ensure_stage_msg(carrier, state: FSMContext, *, text: str,
                           kb=None, parse_mode=None):
    """
    Держим одно «постоянное» сообщение для навигации/этапов и всегда его редактируем.
    """
    msg = carrier.message if hasattr(carrier, "message") else carrier
    bot = msg.bot
    chat_id = msg.chat.id
    data = await state.get_data()
    mid = data.get("stage_msg_id")
    try:
        if mid:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=mid, text=text,
                reply_markup=kb, parse_mode=parse_mode
            )
        else:
            m = await msg.answer(text, reply_markup=kb, parse_mode=parse_mode)
            await state.update_data(stage_msg_id=m.message_id)
    except Exception:
        m = await msg.answer(text, reply_markup=kb, parse_mode=parse_mode)
        await state.update_data(stage_msg_id=m.message_id)

async def ensure_vocab_photo(cb: CallbackQuery, state: FSMContext,
                             img_bytes: bytes, caption: str):
    """
    Картинку словаря держим в отдельном сообщении и каждый раз пересоздаём.
    """
    data = await state.get_data()
    prev_photo_id = data.get("vocab_msg_id")
    if prev_photo_id:
        try:
            await cb.bot.delete_message(
                chat_id=cb.message.chat.id, message_id=prev_photo_id
            )
        except Exception:
            pass
    m = await cb.message.answer_photo(
        photo=BufferedInputFile(img_bytes, filename="vocab.png"),
        caption=caption
    )
    await state.update_data(vocab_msg_id=m.message_id)

# ===== content gen =====
def render_vocab_image(vocab: list) -> bytes:
    W, pad = 1600, 20
    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font_title = ImageFont.load_default()
        font = ImageFont.load_default()

    lines = ["Vocabulary: Mining and Sediments", ""]
    for i, it in enumerate(vocab, 1):
        lines.extend([
            f"{i}. {it['term']}",
            f" • {it['definition']}",
            f" • e.g. {it.get('example','')}",
            ""
        ])

    line_h = 36
    H = pad * 2 + line_h * len(lines)
    img = Image.new("RGB", (W, H), (244, 247, 252))
    draw = ImageDraw.Draw(img)
    y = pad
    draw.text((pad, y), lines[0], font=font_title, fill=(20, 20, 20))
    y += line_h * 2
    for ln in lines[2:]:
        draw.text((pad, y), ln, font=font, fill=(30, 30, 30))
        y += line_h
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio.getvalue()

# ===== DB helpers =====
async def get_lesson(slug: str):
    return await readings_col.find_one({"slug": slug})

async def get_lessons():
    cur = readings_col.find({}, {"_id": 0, "slug": 1, "title": 1})
    return [d async for d in cur]

# ===== entry points =====
@router_reading.message(Command("reading"))
async def reading_entry(m: Message, state: FSMContext):
    lessons = await get_lessons()
    if not lessons:
        await m.answer("Пока нет уроков в разделе Reading.")
        return
    await state.set_state(ReadingFlow.choosing_lesson)
    await m.answer("Выберите урок:", reply_markup=lessons_kb(lessons))

@router_reading.message(Command("reading_debug"))
async def reading_debug(m: Message):
    try:
        pong = await db.command("ping")
        cnt = await readings_col.count_documents({})
        await m.answer(f"ping: {pong.get('ok')}\nDB: {db.name}\nreadings: {cnt}")
    except Exception as e:
        await m.answer(f"DB error: {e}")

@router_reading.callback_query(F.data == "reading:list")
async def reading_list(cb: CallbackQuery, state: FSMContext):
    lessons = await get_lessons()
    await state.set_state(ReadingFlow.choosing_lesson)
    await cb.message.edit_text("Выберите урок:", reply_markup=lessons_kb(lessons))
    await cb.answer()

@router_reading.callback_query(F.data.startswith("reading:open:"))
async def open_lesson(cb: CallbackQuery, state: FSMContext):
    slug = cb.data.split(":")[-1]
    doc = await get_lesson(slug)
    if not doc:
        await cb.answer("Урок не найден", show_alert=True)
        return
    await state.update_data(
        reading_slug=slug, stage_idx=0,
        stage_msg_id=None, quiz_msg_id=None
    )
    await state.set_state(ReadingFlow.in_lesson)
    await send_stage(cb, doc, 0, state)

@router_reading.callback_query(F.data.startswith("reading:nav:"))
async def nav(cb: CallbackQuery, state: FSMContext):
    _, _, slug, idx = cb.data.split(":")
    idx = int(idx)
    doc = await get_lesson(slug)
    if not doc:
        await cb.answer("Урок не найден", show_alert=True)
        return
    await state.update_data(reading_slug=slug, stage_idx=idx)
    await send_stage(cb, doc, idx, state)

# ===== stages rendering =====
async def send_stage(cb: CallbackQuery, doc: dict, idx: int, state: FSMContext):
    stage = STAGES[idx]
    slug = doc["slug"]
    kb = nav_kb(idx, slug)

    if stage == "vocab":
        try:
            img_bytes = render_vocab_image(doc["vocabulary"])
            await ensure_vocab_photo(
                cb, state, img_bytes, f"🧠 Vocabulary — {doc['title']}"
            )
        except Exception:
            pass

        await ensure_stage_msg(
            cb, state,
            text="Нажмите «Далее ➡️», чтобы перейти к тексту.",
            kb=nav_kb(idx, slug),
            parse_mode=None
        )
        await cb.answer()
        return

    if stage == "text":
        text = "\n\n".join(doc["reading_text"])
        await ensure_stage_msg(
            cb, state,
            text=f"📖 *Reading Text*\n\n{text}",
            kb=kb, parse_mode="Markdown"
        )
        await cb.answer()
        return

    if stage == "discussion":
        qs = "\n".join([f"{i+1}. {q}" for i, q in enumerate(doc["discussion_questions"])])
        await ensure_stage_msg(
            cb, state,
            text=f"💬 *Questions for Discussion*\n\n{qs}",
            kb=kb, parse_mode="Markdown"
        )
        await cb.answer()
        return

    if stage == "quiz":
        await ensure_stage_msg(
            cb, state,
            text="📝 Квиз по уроку. Выберите вариант (A/B/C/D).",
            kb=kb
        )
        await start_reading_quiz(cb, doc, state)
        await cb.answer()
        return

    if stage == "task1":
        left = "\n".join([f"{i+1}) {w}" for i, w in enumerate(doc["task1_match"]["left"])])
        right = "\n".join([f"{k}) {v}" for k, v in doc["task1_match"]["right"].items()])
        body = ("🧩 *Task 1. Match the words with their definitions.*\n"
                "Отправьте ответ одной строкой: `1-d, 2-e, 3-h, ...`\n\n"
                f"Список:\n{left}\n\nОпции:\n{right}")
        await ensure_stage_msg(cb, state, text=body, kb=kb, parse_mode="Markdown")
        await cb.answer()
        return

    if stage == "task2":
        bank = ", ".join(doc["task2_fill"]["word_bank"])
        items = "\n".join([f"{it['n']}) {it['text']}" for it in doc["task2_fill"]["items"]])
        body = ("✏️ *Task 2. Fill in the blanks with the correct word.*\n"
                f"Словарик: {bank}\n\n{items}\n\n"
                "Ответ: слова через запятую по порядку (например: `mining, sediment, ...`).")
        await ensure_stage_msg(cb, state, text=body, kb=kb, parse_mode="Markdown")
        await cb.answer()
        return

    if stage == "task3":
        pts = "\n".join([f"{i+1}. {q}" for i, q in enumerate(doc["task3_discussion"])])
        await ensure_stage_msg(
            cb, state,
            text=f"🗣️ *Task 3. Discussion (pair work):*\n\n{pts}",
            kb=kb, parse_mode="Markdown"
        )
        await cb.answer()
        return

# ===== quiz flow =====
def quiz_kb(idx: int) -> InlineKeyboardMarkup:
    letters = ["A", "B", "C", "D"]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=l, callback_data=f"reading:quiz:ans:{idx}:{i}")]
            for i, l in enumerate(letters)
        ]
    )

async def start_reading_quiz(cb: CallbackQuery, doc: dict, state: FSMContext):
    qset = doc["quiz"]
    await state.set_state(ReadingQuiz.current)
    await state.update_data(
        q_index=0, score=0, total=len(qset), qset=qset, quiz_msg_id=None
    )
    await send_quiz_question(cb, qset, 0, state)

async def send_quiz_question(cb: CallbackQuery, qset, idx: int, state: FSMContext):
    data = await state.get_data()
    prev = data.get("quiz_msg_id")
    if prev:
        try:
            await cb.bot.delete_message(chat_id=cb.message.chat.id, message_id=prev)
        except Exception:
            pass
    q = qset[idx]
    text = f"*Q{idx+1}.* {q['q']}\n\n" + "\n".join(
        [f"{chr(65+i)}) {o}" for i, o in enumerate(q["options"])]
    )
    m = await cb.message.answer(text, parse_mode="Markdown", reply_markup=quiz_kb(idx))
    await state.update_data(quiz_msg_id=m.message_id)

from aiogram.exceptions import TelegramBadRequest

@router_reading.callback_query(ReadingQuiz.current, F.data.startswith("reading:quiz:ans:"))
async def reading_quiz_answer(cb: CallbackQuery, state: FSMContext):
    _, _, _, idx, opt = cb.data.split(":")
    idx = int(idx)
    opt = int(opt)

    d = await state.get_data()
    qset = d["qset"]
    correct = qset[idx]["answer_index"]

    # формируем расширенный вердикт: буква + текст варианта
    correct_letter = chr(65 + correct)  # A/B/C/D
    correct_text = qset[idx]["options"][correct]
    # чтобы не уткнуться в пределы длины алёрта — немного ограничим
    MAX = 220
    if len(correct_text) > MAX:
        correct_text = correct_text[:MAX].rstrip() + "…"

    verdict = ("✅ Правильно!"
               if opt == correct
               else f"❌ Правильно: {correct_letter}) {correct_text}")

    # считаем очки
    score = d.get("score", 0) + (1 if opt == correct else 0)
    await state.update_data(score=score)

    next_idx = idx + 1

    if next_idx < len(qset):
        # показываем вердикт по текущему вопросу
        try:
            await cb.answer(verdict, show_alert=True)
        except TelegramBadRequest:
            pass

        # следующий вопрос
        await state.update_data(q_index=next_idx)
        await send_quiz_question(cb, qset, next_idx, state)
        return

    # ===== последний вопрос =====
    total = len(qset)

    # вердикт + итог в одном алёрте
    try:
        await cb.answer(f"{verdict}\n\n🏁 Результат квиза: {score}/{total}", show_alert=True)
    except TelegramBadRequest:
        pass

    # удаляем карточку последнего вопроса
    qid = (await state.get_data()).get("quiz_msg_id")
    if qid:
        try:
            await cb.bot.delete_message(cb.message.chat.id, qid)
        except Exception:
            pass

    # возвращаем навигацию
    data = await state.get_data()
    slug = data.get("reading_slug")
    stage_idx = data.get("stage_idx", 0)
    await ensure_stage_msg(
        cb, state,
        text="Квиз завершён. Нажмите «Далее ➡️», чтобы продолжить.",
        kb=nav_kb(stage_idx, slug)
    )
    await state.set_state(ReadingFlow.in_lesson)


# ===== inputs for task1/task2 =====
@router_reading.message(ReadingFlow.in_lesson)
async def reading_inputs(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return

    data = await state.get_data()
    slug = data.get("reading_slug")
    idx = data.get("stage_idx", 0)
    if not slug:
        return
    doc = await get_lesson(slug)
    if not doc:
        return
    stage = STAGES[idx]

    # не засоряем чат
    try:
        await m.delete()
    except Exception:
        pass

    if stage == "task1":
        ans_map = {
            num: let.lower()
            for (num, let) in re.findall(r"(\d+)\s*[-:]\s*([a-jA-J])", txt)
        }
        key = doc["task1_match"]["answer_key"]
        total = len(key)
        correct = sum(1 for k, v in key.items() if ans_map.get(k, "") == v)
        details = ", ".join([f"{k}-{v}" for k, v in key.items()])
        body = (
            f"🏁 Task 1 — результат: {correct}/{total}\n"
            f"Правильные пары: {details}\n\n"
            f"Нажмите «Далее ➡️», чтобы продолжить."
        )
        await ensure_stage_msg(m, state, text=body, kb=nav_kb(idx, slug))
        return

    if stage == "task2":
        parts = [p.strip().lower() for p in re.split(r"[,\n;]+", txt) if p.strip()]
        items = doc["task2_fill"]["items"]
        total = len(items)
        correct = 0
        rows = []
        for i, it in enumerate(items):
            gold = (it["answer"] or "").lower()
            guess = parts[i] if i < len(parts) else ""
            ok = (guess == gold)
            correct += int(ok)
            rows.append(f"{i+1}) {'✅' if ok else '❌'} {guess or '—'} (ans: {gold})")
        body = "🏁 Task 2 — результат: {}/{}\n\n{}\n\nНажмите «Далее ➡️», чтобы продолжить.".format(
            correct, total, "\n".join(rows)
        )
        await ensure_stage_msg(m, state, text=body, kb=nav_kb(idx, slug))
        return
