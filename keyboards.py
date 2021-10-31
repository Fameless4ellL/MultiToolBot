from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton

inline_btn_1 = InlineKeyboardButton('Scan', callback_data='scan', )
inline_btn_7 = InlineKeyboardButton('QRcode', callback_data='qrcode', )
inline_kb1 = InlineKeyboardMarkup().add(inline_btn_1, inline_btn_7)

inline_btn_2 = InlineKeyboardButton('pdf version', callback_data='pdf')
inline_kb2 = InlineKeyboardMarkup().add(inline_btn_2)

inline_btn_3 = InlineKeyboardButton('Остановить', callback_data='CancelTimer')
inline_kb3 = InlineKeyboardMarkup().add(inline_btn_3)

inline_btn_4 = InlineKeyboardButton('Calendar', callback_data='Navigation Calendar')
inline_kb4 = InlineKeyboardMarkup().add(inline_btn_4)

inline_btn_5 = InlineKeyboardButton('Title', callback_data='Title_rm')
# inline_btn_6 = InlineKeyboardButton('Date', callback_data='Date_rm')
inline_kb6 = InlineKeyboardMarkup().add(inline_btn_5)
