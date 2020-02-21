###########
# Imports #
###########

# General
from datetime import datetime
import itertools
import json
import logging
import socket
import threading

# Firebase database
from firebase_admin import db, credentials, initialize_app

# Telegram communication
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, \
    RegexHandler, MessageHandler, Filters

#############
# Constants #
#############

# SENSITIVE!
TELEGRAM_API = "977440557:AAHegnFH7EbLv4X1xlwtJJU-o1jZfUKMWF0"  # @gvora_bot
FIREBASE_CERTIF = 'gvurapp-firebase-adminsdk-dple5-31000da37d.json'
FIREBASE_URL = 'https://gvurapp.firebaseio.com/'
FIREBASE_REF = '1U03j2esstu_1xXvdNcuNOoNhTbP7B4bVETsLuZUEtbU'

# non-sensitive
STR_WEEKS_2 = "עוד שבועיים"
STR_WEEKS_1 = "שבוע הבא"
STR_WEEKS_0 = "השבוע"
STR_ENTRY_TEXT = "\U00002705 *{event[Name]}*\n_{event[Location]}\n{event[date]}_\n{event[info]}\nלרישום: /reg{event[id]}\n\n"
STR_SEARCH_DISPLAY = "search_display"
STR_SEARCH_PAGE = "search_page"
STR_REGISTER_GOOD = "הרישום התקבל!"
STR_NO_RESULTS = "אין תוצאות"
STR_SEARCH = 'search'
STR_START = 'start'
START_MESSAGE_1 = """
אנחנו מזמינים אותך לקחת חלק בפרויקט הלאומי של התנדבות למען שורדי השואה ולהשתתף במסורת של עשייה והנצחה אקטיבית!
לרישום למאגר המתנדבים לחץ כאן: https://bit.ly/2SmK79L
"""
START_MESSAGE_2 = """
שלח /search על מנת להתחיל בחיפוש הזדמנויות התנדבות.
"""


###########
# Methods #
###########

def build_menu(current_page, max_page, header_buttons=None,
               footer_buttons=None):
    navigation_buttons = [
        InlineKeyboardButton(
            "1 <<", callback_data="first_page"),
        InlineKeyboardButton(
            "{} <".format(max(current_page, 1)), callback_data="prev_page"),
        InlineKeyboardButton(
            "{}".format(current_page + 1), callback_data="."),
        InlineKeyboardButton(
            "> {}".format(min(current_page + 2, max_page + 1)),
            callback_data="next_page"),
        InlineKeyboardButton(
            ">> {}".format(max_page + 1), callback_data="last_page")
    ]

    date_buttons = [
        InlineKeyboardButton(STR_WEEKS_0, callback_data="filter_week_0"),
        InlineKeyboardButton(STR_WEEKS_1, callback_data="filter_week_1"),
        InlineKeyboardButton(STR_WEEKS_2, callback_data="filter_week_2")
    ]

    menu = [navigation_buttons, date_buttons]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


def start(update, context):
    user = update.message.from_user
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=START_MESSAGE_1)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=START_MESSAGE_2)

    context.user_data[STR_SEARCH_PAGE] = 0


def get_all_events():
    new_volunteer_events = ref.child("Events").get()[1:]
    for i in range(len(new_volunteer_events)):
        new_volunteer_events[i]["date"] = datetime.fromisoformat(
            new_volunteer_events[i]["date"][:-1])
    return new_volunteer_events


def get_page_text(events):
    template = STR_ENTRY_TEXT
    text = ""
    for event in events:
        text += template.format(event=event)
    return text


def filter_events_by_week(events, week_diff):
    cur_time = datetime.now()
    events_filtered = []
    for event in events:
        if week_diff * 7 <= (event["date"] - cur_time).days < (
                week_diff + 1) * 7:
            events_filtered.append(event)
    return events_filtered


def repeated_to_pages(events, elemnts_in_page):
    return [events[x:x + elemnts_in_page] for x in
            range(0, len(events), elemnts_in_page)]


def button_pressed(update, context):
    query = update.callback_query
    context.bot.answer_callback_query(query.id)

    search_display = context.user_data[STR_SEARCH_DISPLAY]
    search_page = context.user_data[STR_SEARCH_PAGE]

    if query.data.endswith("page"):
        if query.data.startswith("next") and search_page + 1 != len(
                search_display) and len(search_display) != 0:
            search_page += 1
        elif query.data.startswith("prev") and search_page != 0 and len(
                search_display) != 0:
            search_page -= 1
        elif query.data.startswith("first") and search_page != 0 and len(
                search_display) != 0:
            search_page = 0
        elif query.data.startswith("last") and search_page != len(
                search_display) - 1 and len(search_display) != 0:
            search_page = len(search_display) - 1

        reply_markup = InlineKeyboardMarkup(
            build_menu(search_page, len(search_display) - 1))
        text = get_page_text(search_display[search_page])
        query.edit_message_text(text=text, reply_markup=reply_markup,
                                parse_mode=telegram.ParseMode.MARKDOWN)
    elif query.data.startswith("filter"):
        events = filter_events_by_week(volunteer_events,
                                       int(query.data.split("_")[2]))
        search_display = repeated_to_pages(events, 3)

        if len(search_display) == 0 and len(
                context.user_data[STR_SEARCH_DISPLAY]) == 0:
            return

        context.user_data[STR_SEARCH_DISPLAY] = search_display
        search_page = 0

        if len(search_display) == 0:
            text = STR_NO_RESULTS
        else:
            text = get_page_text(search_display[search_page])

        reply_markup = InlineKeyboardMarkup(
            build_menu(search_page, max(len(search_display) - 1, 0)))
        query.edit_message_text(text=text, reply_markup=reply_markup,
                                parse_mode=telegram.ParseMode.MARKDOWN)
    context.user_data[STR_SEARCH_PAGE] = search_page


def search(update, context):
    volunteer_events = get_all_events()
    search_display = repeated_to_pages(volunteer_events, 3)
    search_page = 0

    context.user_data[STR_SEARCH_PAGE] = search_page
    context.user_data[STR_SEARCH_DISPLAY] = search_display

    reply_markup = InlineKeyboardMarkup(
        build_menu(search_page, len(search_display) - 1))
    text = get_page_text(search_display[search_page])
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=reply_markup,
                             parse_mode=telegram.ParseMode.MARKDOWN)


def register(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=STR_REGISTER_GOOD)


########
# Main #
########

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
firebase_app = initialize_app(credentials.Certificate(
    FIREBASE_CERTIF))
ref = db.reference(FIREBASE_REF,
                   app=firebase_app, url=FIREBASE_URL)

volunteer_events = []

updater = Updater(token=API_TOKEN, use_context=True)
dispatcher = updater.dispatcher
dispatcher.add_handler(CommandHandler(STR_START, start))
dispatcher.add_handler(CommandHandler(STR_SEARCH, search))
dispatcher.add_handler(
    MessageHandler(Filters.regex('^(/reg[\d]+)$'), register))
dispatcher.add_handler(MessageHandler(Filters.text, echo))
dispatcher.add_handler(CallbackQueryHandler(button_pressed))

volunteer_events = get_all_events()
updater.job_queue.run_repeating(callback_minute, interval=60, first=0)
updater.start_polling()
updater.idle()
