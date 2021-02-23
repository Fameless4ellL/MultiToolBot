from flask import Flask, request
import telegram
import os
import json

TOKEN = os.environ['TOKEN']
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)


@app.route('/{}'.format(TOKEN), methods=['POST'])
def respond():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    chat_id = update.message.chat.id
    msg_id = update.message.message_id
    msg = update.message.text.encode('utf-8').decode()
    bot.sendMessage(chat_id=chat_id, text=msg, reply_to_message_id=msg_id)
    return 'ok'


@app.route('/', methods=['POST'])
def index():
    return 'ok'


if __name__ == '__main__':
    app.run(threaded=True)
