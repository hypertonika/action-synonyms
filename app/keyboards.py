from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/help"), KeyboardButton(text="/start")],
        [KeyboardButton(text="/list"), KeyboardButton(text="/add_word")],
        [KeyboardButton(text="/random_word"), KeyboardButton(text="/flashcards")],
        [KeyboardButton(text="/start_quiz"), KeyboardButton(text="/reading")],  # Новая кнопка для случайного слова
    ],
    resize_keyboard=True,  # Уменьшает размер кнопок для удобства
    one_time_keyboard=False  # Клавиатура останется на экране после нажатия
)
