# app/listening.py
import re
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.testhandle import db  # как в reading.py

listenings_col = db["listenings"]
router_listening = Router()


# ===== FSM =====
class ListeningFlow(StatesGroup):
    choosing_lesson = State()
    in_lesson = State()


STAGES = ["audio", "questions", "gaps"]


# ===== UI helpers =====
def nav_kb(stage_idx: int, slug: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    if stage_idx > 0:
        row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"listening:nav:{slug}:{stage_idx-1}",
            )
        )
    if stage_idx < len(STAGES) - 1:
        row.append(
            InlineKeyboardButton(
                text="Далее ➡️",
                callback_data=f"listening:nav:{slug}:{stage_idx+1}",
            )
        )
    if row:
        rows.append(row)

    rows.append(
        [InlineKeyboardButton(text="🎧 К списку listening", callback_data="listening:list")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lessons_kb(lessons: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ls.get("title", "(no title)"),
                    callback_data=f"listening:open:{ls['slug']}",
                )
            ]
            for ls in lessons
        ]
    )


async def ensure_stage_msg(
    carrier, state: FSMContext, *, text: str, kb: InlineKeyboardMarkup | None = None, parse_mode: str | None = None
):
    """
    Как в reading.py: редактируем существующее сообщение или создаем новое.
    """
    msg = carrier.message if hasattr(carrier, "message") else carrier
    bot = msg.bot
    chat_id = msg.chat.id
    data = await state.get_data()
    mid = data.get("listening_stage_msg_id")

    try:
        if mid:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=mid,
                text=text,
                reply_markup=kb,
                parse_mode=parse_mode,
            )
        else:
            m = await msg.answer(text, reply_markup=kb, parse_mode=parse_mode)
            await state.update_data(listening_stage_msg_id=m.message_id)
    except Exception:
        m = await msg.answer(text, reply_markup=kb, parse_mode=parse_mode)
        await state.update_data(listening_stage_msg_id=m.message_id)


# ===== DB helpers =====
async def get_lesson(slug: str):
    return await listenings_col.find_one({"slug": slug}, {"_id": 0})


async def get_lessons():
    cur = listenings_col.find({}, {"_id": 0, "slug": 1, "title": 1})
    return [d async for d in cur]


# ===== entry points =====
@router_listening.message(Command("listening"))
async def listening_entry(m: Message, state: FSMContext):
    lessons = await get_lessons()
    if not lessons:
        await m.answer("Пока нет заданий в разделе Listening.")
        return

    await state.set_state(ListeningFlow.choosing_lesson)
    await m.answer("Выберите аудио-задание:", reply_markup=lessons_kb(lessons))


@router_listening.callback_query(F.data == "listening:list")
async def listening_list(cb: CallbackQuery, state: FSMContext):
    lessons = await get_lessons()
    await state.set_state(ListeningFlow.choosing_lesson)
    await cb.message.edit_text(
        "Выберите аудио-задание:", reply_markup=lessons_kb(lessons)
    )
    await cb.answer()


@router_listening.callback_query(F.data.startswith("listening:open:"))
async def listening_open(cb: CallbackQuery, state: FSMContext):
    slug = cb.data.split(":")[-1]
    doc = await get_lesson(slug)
    if not doc:
        await cb.answer("Урок не найден", show_alert=True)
        return

    await state.update_data(
        listening_slug=slug, listening_stage_idx=0, listening_stage_msg_id=None
    )
    await state.set_state(ListeningFlow.in_lesson)
    await send_stage(cb, doc, 0, state)


@router_listening.callback_query(F.data.startswith("listening:nav:"))
async def listening_nav(cb: CallbackQuery, state: FSMContext):
    _, _, slug, idx = cb.data.split(":")
    idx = int(idx)
    doc = await get_lesson(slug)
    if not doc:
        await cb.answer("Урок не найден", show_alert=True)
        return

    await state.update_data(listening_slug=slug, listening_stage_idx=idx)
    await send_stage(cb, doc, idx, state)


# ===== stages rendering =====
async def send_stage(cb: CallbackQuery, doc: dict, idx: int, state: FSMContext):
    stage = STAGES[idx]
    slug = doc["slug"]
    kb = nav_kb(idx, slug)

    # 1) Аудио
    if stage == "audio":
        # Отправляем голосовое как «круглое» сообщение
        audio_file_id = doc["audio_file_id"]
        await cb.message.answer_voice(
            voice=audio_file_id,
            caption=f"🎧 Listening — {doc['title']}",
        )

        await ensure_stage_msg(
            cb,
            state,
            text="Прослушайте аудио, затем нажмите «Далее ➡️», чтобы перейти к заданиям.",
            kb=kb,
        )
        await cb.answer()
        return

    # 2) Вопросы на понимание
    if stage == "questions":
        qs = "\n".join(
            [f"{i+1}. {q}" for i, q in enumerate(doc.get("questions", []))]
        )
        body = (
            "❓ *Listening comprehension questions*\n\n"
            f"{qs}"
        )
        await ensure_stage_msg(
            cb, state, text=body, kb=kb, parse_mode="Markdown"
        )
        await cb.answer()
        return

    # 3) Fill in the gaps
    if stage == "gaps":
        items = doc.get("gaps", {}).get("items", [])
        text_lines = [f"{it['n']}) {it['text']}" for it in items]
        body = (
            "✏️ *Fill in the gaps.*\n"
            "Напишите ответы в одном сообщении через запятую в правильном порядке.\n"
            "Например: `action, synonyms, example, ...`\n\n"
            + "\n".join(text_lines)
        )
        await ensure_stage_msg(
            cb, state, text=body, kb=kb, parse_mode="Markdown"
        )
        await cb.answer()
        return


# ===== input handler for gaps =====
@router_listening.message(ListeningFlow.in_lesson)
async def listening_inputs(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if txt.startswith("/"):
        return

    data = await state.get_data()
    slug = data.get("listening_slug")
    idx = data.get("listening_stage_idx", 0)
    if not slug:
        return

    doc = await get_lesson(slug)
    if not doc:
        return

    stage = STAGES[idx]

    # удаляем ответ пользователя, чтобы чат не захламлять
    try:
        await m.delete()
    except Exception:
        pass

    # Проверяем только на этапе gaps
    if stage != "gaps":
        # Для questions можно просто оставить их в чате как дискуссию
        return

    # парсим ответы
    parts = [
        p.strip().lower() for p in re.split(r"[,\n;]+", txt) if p.strip()
    ]
    items = doc.get("gaps", {}).get("items", [])
    total = len(items)
    correct = 0
    rows = []

    for i, it in enumerate(items):
        gold = (it.get("answer") or "").lower()
        guess = parts[i] if i < len(parts) else ""
        ok = guess == gold
        if ok:
            correct += 1
        rows.append(
            f"{i+1}) {'✅' if ok else '❌'} {guess or '—'} (ans: {gold})"
        )

    body = "🏁 Listening — gaps result: {}/{}\n\n{}\n\nНажмите «Назад» или «🎧 К списку listening», чтобы выбрать другое задание.".format(
        correct, total, "\n".join(rows)
    )

    kb = nav_kb(idx, slug)
    await ensure_stage_msg(m, state, text=body, kb=kb)
