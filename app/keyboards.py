from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/help"), KeyboardButton(text="/start")],
        [KeyboardButton(text="/list"), KeyboardButton(text="/add_word")],
        [KeyboardButton(text="/random_word"), KeyboardButton(text="/flashcards")],
        [KeyboardButton(text="/start_quiz"), KeyboardButton(text="/reading")],
        [KeyboardButton(text="/listening")],
        [KeyboardButton(text="Для преподавателя"), KeyboardButton(text="О боте")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)
