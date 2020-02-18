import json
import os.path
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from telegram.utils.request import Request as TelegramRequest
from telegram import Bot
from google_auth_oauthlib.flow import Flow
import base64
import sqlalchemy as db
import os
import ast


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class EmailBotService:
    """Service for communicate with bot and gmail."""

    LISTEN = 0
    SECRET_KEY = ''

    def __init__(self, access_token: str):
        """Initialize bot work."""

        self.access_token = access_token

        self.req = TelegramRequest(
            connect_timeout=0.5,
            read_timeout=1.0,
        )
        self.bot = Bot(
            token=self.access_token,
            request=self.req)

        self.updater = Updater(bot=self.bot, use_context=True)
        self.track_message = None
        self.chat_id = self.updater.bot

        start_handler = CommandHandler(command="start",
                                       callback=self.start_command)
        get_message_handler = CommandHandler(command="getmessage",
                                             callback=self.getmessage)
        register_manager_handler = CommandHandler(command='register_manager',
                                                  callback=self.register_manager)
        cancel_hand = CommandHandler(command='cancel',
                                     callback=self.cancel_handler)
        conversation_handler = ConversationHandler(
            entry_points=[CommandHandler('ask_keys', self.ask_keys)],
            states={self.LISTEN: [MessageHandler(Filters.text, self.get_keys, pass_user_data=True)]},
            fallbacks=[cancel_hand])

        self.updater.dispatcher.add_handler(start_handler)
        self.updater.dispatcher.add_handler(get_message_handler)
        self.updater.dispatcher.add_handler(register_manager_handler)
        self.updater.dispatcher.add_handler(conversation_handler)

    def ask_keys(self, update, context):
        """method to request a new key input"""
        update.message.reply_text('Введите новый ключ')
        return self.LISTEN

    def get_keys(self, update, context):
        """method to get user input"""
        self.SECRET_KEY = update.message.text
        update.message.reply_text(text=f'Новый ключ: {self.SECRET_KEY}')
        return ConversationHandler.END

    def cancel_handler(self, update, context):
        update.message.reply_text('Отмена. Для изменения ключей нажмите /ask_keys')
        return ConversationHandler.END

    def run_bot(self):
        """Running bot."""

        TOKEN = self.access_token
        PORT = int(os.environ.get('PORT', '8443'))

        self.updater.start_webhook(listen="0.0.0.0",
                                   port=PORT,
                                   url_path=TOKEN)
        self.updater.bot.set_webhook("https://botdenysdashadasha.herokuapp.com/" + TOKEN)
        self.updater.idle()

    def register_manager(self, update, context):
        """method to add chat id to managers.jso"""
        new_manager_chat_id = update['message']['chat']['id']
        new_manager_name = update['message']['chat']['first_name']

        with open('managers.json') as obj:
            managers = json.load(obj)

        managers[new_manager_name] = new_manager_chat_id

        with open('managers.json', 'w') as obj:
            json.dump(managers, obj)

        context.bot.send_message(chat_id=update.message.chat_id, text=f'{new_manager_name} - {new_manager_chat_id}')

    def getmessage(self, update, context):
        """execute message uploading process"""

        redirect_uri = "https://thawing-ridge-47246.herokuapp.com"

        # настройка соединения
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri=redirect_uri)

        code = self.get_code()

        flow.fetch_token(code=code, code_verifier="111")  # устанавливаем соединение с гуглом

        session = flow.authorized_session()  # создаем сессию
        response = session.get('https://www.googleapis.com/gmail/v1/users/me/messages').json()  # формируем запрос и получаем ответ сервера

        messages = response["messages"]

        # у каждого из сообщений достаем id
        for message in messages[0:10]:
            mid = message['id']

            # получаем сообщение по id
            message_message = session.get(f'https://www.googleapis.com/gmail/v1/users/me/messages/{mid}').json()

            # информация об отправителе, получателе и теме сообщения хранится в ключе 'payload' --> 'headers'
            headers = message_message['payload']['headers']

            from_who = None
            to_whom = None
            subject = None

            for item in headers:
                if item['name'] == 'From':
                    from_who = item['value']
                elif item['name'] == 'To':
                    to_whom = item['value']
                elif item['name'] == 'Subject':
                    subject = item['value']

            # ищем текст сообщения
            # достаем из сообщения его части
            message_payload_parts = message_message['payload']['parts']
            zero_part = message_payload_parts[0]

            if zero_part['mimeType'] == 'text/plain':
                self.message_without_attachments(context, message_payload_parts, from_who, to_whom, subject)
            elif zero_part['mimeType'] == 'multipart/alternative':
                self.message_with_attachments(session, mid, context, zero_part, message_payload_parts, from_who,
                                              to_whom, subject)

        context.bot.send_message(chat_id=update.message.chat_id, text=f'Done.')

    def get_code(self):
        """method to get authorization code"""
        # подключаемся к базе данных хероку, чтобы вытащить крайний ключ-код
        engine = db.create_engine('postgresql+psycopg2://vxttrrwzkdeaol:367054ad01122101b1b5d9'
                                  'ee099e03253d212ec914e330378952dec6c67e5174@ec2-79-125-126-20'
                                  '5.eu-west-1.compute.amazonaws.com/d82qavso2hgauu')

        connection = engine.connect()  # устанавливаем соединение
        metadata = db.MetaData()

        # из всех существующих таблиц выбираем нужную: 'hola_bottable'
        hola_bottable = db.Table('hola_bottable', metadata, autoload=True, autoload_with=engine)

        # Equivalent to 'SELECT * FROM census'
        query = db.select([hola_bottable])
        ResultProxy = connection.execute(query)
        ResultSet = ResultProxy.fetchall()  # возвращает список из tuple формата [(id:..., code:...)]

        code = ResultSet[-1][1]  # из списка строк выбираем последнюю
        return code

    def message_without_attachments(self, context, message_payload_parts, from_who, to_whom, subject):
        """method to get Gmail message without attachments"""

        body_of_part = None

        # достаем из нужной части (текст сообщения хранится под нулевым индексом) текст сообщения закодированный в
        # формате "utf-8" и "base64"
        for part in message_payload_parts:
            if part['partId'] == '0':
                body_of_part = part['body']

        # декодируем
        encoded_text = body_of_part['data']
        decodedBytes = base64.urlsafe_b64decode(encoded_text)
        decoded_text = str(decodedBytes, "utf-8")  # текст сообщения сохраняем в переменную

        if self.SECRET_KEY in subject or self.SECRET_KEY in decoded_text:

            telebot_message_text = f'Sender: {from_who}.\n' \
                                   f'Receiver: {to_whom}.\n' \
                                   f'Subject: {subject}.\n' \
                                   f'Text of message: {decoded_text}'

            with open('managers.json') as obj:
                managers = json.load(obj)

            for m_chat_id in managers.values():
                try:
                    context.bot.send_message(chat_id=m_chat_id, text=telebot_message_text)  # отправка сообщения в бот
                except:
                    pass

    def message_with_attachments(self, session, mid, context, zero_part, message_payload_parts,
                                 from_who, to_whom, subject):
        """method to get Gmail message with attachments"""

        zero_part_parts = zero_part['parts']
        sub_zero_part = zero_part_parts[0]
        body_of_part = sub_zero_part['body']

        # декодируем
        encoded_text = body_of_part['data']
        decodedBytes = base64.urlsafe_b64decode(encoded_text)
        decoded_text = str(decodedBytes, "utf-8")  # текст сообщения сохраняем в переменную

        if self.SECRET_KEY in subject or self.SECRET_KEY in decoded_text:

            telebot_message_text = f'Sender: {from_who}.\n' \
                                   f'Receiver: {to_whom}.\n' \
                                   f'Subject: {subject}.\n' \
                                   f'Text of message: {decoded_text}'

            with open('managers.json') as obj:
                managers = json.load(obj)

            for m_chat_id in managers.values():
                try:
                    context.bot.send_message(chat_id=m_chat_id, text=telebot_message_text)  # отправка сообщения в бот
                except:
                    pass

                self.get_and_send_attachments(session, mid, message_payload_parts, context, m_chat_id)

    def get_and_send_attachments(self, session, mid, message_payload_parts, context, m_chat_id):
        """method to and send Gmail attachments"""

        store_dir_1 = os.getcwd()

        for part in message_payload_parts:
            if part['filename']:
                attachment_id = part['body']['attachmentId']

                response = session.get(f'https://www.googleapis.com/gmail/v1/users/me/'
                                       f'messages/{mid}/attachments/{attachment_id}')

                data = response.content
                encoded_data_dict = ast.literal_eval(data.decode('utf-8'))
                file_data = base64.urlsafe_b64decode(encoded_data_dict['data'].encode('UTF-8'))

                path = os.path.join(store_dir_1, part['filename'])

                # запись данных в файловую систему, чтение, отправка и удаление
                with open(path, 'wb') as file_object:
                    file_object.write(file_data)
                with open(path, 'rb') as f:
                    context.bot.send_document(m_chat_id, f)
                os.remove(path)

    def start_command(self, update, context):
        """Bot start command"""

        redirect_uri = "https://thawing-ridge-47246.herokuapp.com"
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        flow.code_verifier = "111"

        # Tell the user to go to the authorization URL.
        auth_url, _ = flow.authorization_url(prompt='consent',  access_type='offline', include_granted_scopes='true')

        telebot_message_text = 'Please go to this URL: {}'.format(auth_url)
        context.bot.send_message(chat_id=update.message.chat_id, text=telebot_message_text)







