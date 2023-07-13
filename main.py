import datetime
import random

import requests
import database
from telebot.storage import StateMemoryStorage
import settings
import telebot
import models
from telebot import types
from loguru import logger
from telebot.types import Message, Dict, CallbackQuery, InputMediaPhoto
from settings import BOT_TOKEN, DEFAULT_COMMANDS
from telebot.custom_filters import StateFilter
from telebot.types import BotCommand
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP

storage = StateMemoryStorage()
bot = telebot.TeleBot(token=BOT_TOKEN, state_storage=storage)

# logger.remove(handler_id=None)  # отмена вывода в консоль
logger.add("runtime.log")  # создание журнала
logger.info('Начало журнала')

headers = {
    "content-type": "application/json",
    "X-RapidAPI-Key": settings.RAPID_API_KEY,
    "X-RapidAPI-Host": "hotels4.p.rapidapi.com",
}


def set_default_commands(bot):
    bot.set_my_commands(
        [BotCommand(*i) for i in DEFAULT_COMMANDS]
    )


@bot.message_handler(commands=['start'])
@logger.catch
def bot_start(message: Message) -> None:
    """
    Функция, реагирующая на команду 'start'. Выводит приветственное сообщение.

    :param message: сообщение Telegram
    """

    bot.delete_state(message.from_user.id, message.chat.id)
    bot.send_message(message.chat.id, f"👋 Привет, {message.from_user.username}!\n"
                                      f"Можете ввести какую-нибудь команду!\n")


@bot.message_handler(commands=['help'])  # +
def bot_help(message: Message):
    text = [f'/{command} - {desk}' for command, desk in DEFAULT_COMMANDS]
    bot.reply_to(message, '\n'.join(text))


@bot.message_handler(commands=['history'])
def history(message: Message) -> None:
    """
        Обработчик команд, срабатывает на команду /history
        Обращается к базе данных и выдает в чат запросы пользователя
        по отелям.
        : param message : Message
        : return : None
    """
    logger.info('Выбрана команда history!')
    queries = database.read_query(message.chat.id)
    logger.info(f'Получены записи из таблицы query:\n {queries}')
    for item in queries:
        bot.send_message(message.chat.id, f"({item[0]}). Дата и время: {item[1]}. Вы вводили город: {item[2]}")
    bot.set_state(message.chat.id, models.UserInputState.history_select)
    bot.send_message(message.from_user.id, "Введите номер интересующего вас варианта: ")


@bot.message_handler(state=models.UserInputState.history_select)
def input_city(message: Message) -> None:
    """
        Ввод пользователем номера запроса, которые есть в списке. Если пользователь введет
        неправильный номер или это будет "не цифры", то бот попросит повторить ввод.
        Запрос к базе данных нужных нам записей. Выдача в чат результата.
        : param message : Message
        : return : None
    """
    if message.text.isdigit():
        queries = database.read_query(message.chat.id)
        number_query = []
        photo_need = ''
        for item in queries:
            number_query.append(item[0])
            if int(message.text) == item[0] and item[3] == 'yes':
                photo_need = 'yes'

        if photo_need != 'yes':
            bot.send_message(message.chat.id, 'Пользователь выбирал вариант "без фото"')

        if int(message.text) in number_query:
            history_dict = database.get_history_response(message.text)
            logger.info('Выдаем результаты выборки из базы данных')
            for hotel in history_dict.items():
                medias = []
                caption = f"Название отеля: {hotel[1]['name']}]\n Адрес отеля: {hotel[1]['address']}" \
                          f"\nСтоимость проживания в " \
                          f"сутки $: {hotel[1]['price']}\nРасстояние до центра: {hotel[1]['distance']}"
                urls = hotel[1]['images']
                if photo_need == 'yes':
                    for number, url in enumerate(urls):
                        if number == 0:
                            medias.append(InputMediaPhoto(media=url, caption=caption))
                        else:
                            medias.append(InputMediaPhoto(media=url))
                    bot.send_media_group(message.chat.id, medias)
                else:
                    bot.send_message(message.chat.id, caption)
        else:
            bot.send_message(message.chat.id, 'Ошибка! Вы ввели число, которого нет в списке! Повторите ввод!')
    else:
        bot.send_message(message.chat.id, 'Ошибка! Вы ввели не число! Повторите ввод!')


@bot.message_handler(commands=['simple_history'])  # +
def bot_history(message: Message):
    logger.info('Выбрана команда simple_history!')
    with open('log.txt', 'r') as log:
        text = [f'{string}' for string in log.readlines()]
    bot.reply_to(message, '\n'.join(text))


@bot.message_handler(commands=["lowprice", "highprice", "bestdeal"])  # +
def common_handler(message: Message):
    bot.set_state(message.chat.id, models.UserInputState.command)  # принимаем сообщение от user
    with bot.retrieve_data(message.chat.id) as data:
        data.clear()
        logger.info(f'{datetime.datetime.now()} Пользовательский запрос:' + message.text)
        data['command'] = message.text
        data['sort'] = check_command(message.text)
        data['date_time'] = datetime.datetime.now().strftime('%D.%M.%Y. %H:%M:%S')
        data['chat_id'] = message.chat.id
    database.add_user(message.chat.id, message.from_user.username, message.from_user.full_name)
    bot.set_state(message.chat.id, models.UserInputState.input_city)
    bot.send_message(message.from_user.id, 'В каком городе вы желаете найти отель?')


@bot.message_handler(state=models.UserInputState.input_city)  # +
def input_city(message: Message):
    with bot.retrieve_data(message.chat.id) as data:
        data['input_city'] = message.text
        logger.info('Пользователь выбрал город ' + message.text)
        url = "https://hotels4.p.rapidapi.com/locations/v3/search"
        querystring = {"q": message.text, "locale": "en_US"}
        response_cities = settings.gen_request('GET', url, querystring)
        if response_cities.status_code == 200:
            logger.info('Ответ сервера: 200')
            possible_cities = models.get_city(response_cities.text)
            models.show_cities_buttons(message, possible_cities)
        else:
            logger.info('Ошибка при выборе города ' + message.text)
            bot.send_message(message.chat.id, f"Что-то пошло не так, код ошибки: {response_cities.status_code}")
            bot.send_message(message.chat.id, "Выберите город еще раз")
            data.clear()


def show_cities(message: Message, possible_cities: Dict):  # +
    logger.info('Вывод вариантов городов пользователю')
    keyboards_cities = types.InlineKeyboardMarkup()
    for key, values in possible_cities.items():
        keyboards_cities.add(types.InlineKeyboardButton(text=values["region"], callback_data=values["gaiaID"]))
    bot.send_message(message.from_user.id, "Выберите город", reply_markup=keyboards_cities)


@bot.callback_query_handler(func=lambda call: call.data.isdigit())  # +
def destination_id_callback(call: CallbackQuery):
    logger.info(f'Пользователь выбрал город: {call.message.chat.id}')
    if call.data:
        bot.set_state(call.message.chat.id, models.UserInputState.destinationId)
        with bot.retrieve_data(call.message.chat.id) as data:
            data['destination_id'] = call.data
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.set_state(call.message.chat.id, models.UserInputState.quantity_hotels)
        bot.send_message(call.message.chat.id, 'Выберите количество отелей для просмотра')


@bot.message_handler(state=models.UserInputState.quantity_hotels)  # +
def input_quantity(message: Message):
    if message.text.isdigit():
        if 0 < int(message.text) <= 25:
            logger.info('Ввод и запись количества отелей: ' + message.text)
            with bot.retrieve_data(message.chat.id) as data:
                data['quantity_hotels'] = message.text
            bot.set_state(message.chat.id, models.UserInputState.priceMin)
            bot.send_message(message.chat.id, 'Введите минимальную стоимость отеля в долларах США:')
        else:
            bot.send_message(message.chat.id, 'Ошибка! Это должно быть число в диапазоне от 1 до 25! Повторите ввод!')
    else:
        bot.send_message(message.chat.id, 'Ошибка! Вы ввели не число! Повторите ввод!')


@bot.message_handler(state=models.UserInputState.priceMin)  # +
def input_price_min(message: Message):
    if message.text.isdigit():
        logger.info('Ввод и запись минимальной стоимости отеля: ' + message.text)
        with bot.retrieve_data(message.chat.id) as data:
            data['price_min'] = message.text
        bot.set_state(message.chat.id, models.UserInputState.priceMax)
        bot.send_message(message.chat.id, 'Введите максимальную стоимость отеля в долларах США:')
    else:
        bot.send_message(message.chat.id, 'Ошибка! Вы ввели не число! Повторите ввод!')


@bot.message_handler(state=models.UserInputState.priceMax)
def input_price_max(message: Message):
    if message.text.isdigit():
        logger.info('Ввод и запись максимальной стоимости отеля, сравнение с price_min: ' + message.text)
        with bot.retrieve_data(message.chat.id) as data:
            if int(data['price_min']) < int(message.text):
                data['price_max'] = message.text
            else:
                bot.send_message(message.chat.id, 'Максимальная цена должна быть больше минимальной. Повторите ввод!')

    else:
        bot.send_message(message.chat.id, 'Ошибка! Вы ввели не число! Повторите ввод!')

    calendar, step = DetailedTelegramCalendar(calendar_id=1, min_date=datetime.date.today()).build()
    bot.send_message(message.chat.id, f"Выберите дату заселения {LSTEP[step]}", reply_markup=calendar)
    bot.set_state(message.chat.id, models.UserInputState.checkInDate)


@bot.callback_query_handler(func=DetailedTelegramCalendar.func(calendar_id=1), state=models.UserInputState.checkInDate)
def check_in(call: CallbackQuery) -> None:
    result, key, step = DetailedTelegramCalendar(
        calendar_id=1,
        locale='ru',
        min_date=datetime.date.today()).process(call.data)
    if not result and key:
        bot.edit_message_text(f"Выберите {LSTEP[step]}",
                              call.message.chat.id,
                              call.message.message_id,
                              reply_markup=key)
    elif result:
        bot.set_state(call.message.chat.id, models.UserInputState.checkInDate)
        with bot.retrieve_data(call.message.chat.id) as data:
            data['checkInDate'] = result
        bot.send_message(call.message.chat.id, f"Дата заезда в отель: {result}")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        calendar, step = DetailedTelegramCalendar(calendar_id=2, min_date=datetime.date.today()).build()
        bot.send_message(call.message.chat.id, f"Выберите дату выезда из отеля {LSTEP[step]}", reply_markup=calendar)
        bot.set_state(call.message.chat.id, models.UserInputState.checkOutDate)


@bot.callback_query_handler(func=DetailedTelegramCalendar.func(calendar_id=2), state=models.UserInputState.checkOutDate)
def check_out(call: CallbackQuery) -> None:
    result, key, step = DetailedTelegramCalendar(
        calendar_id=2,
        locale='ru',
        min_date=datetime.date.today()).process(call.data)
    if not result and key:
        bot.edit_message_text(f"Выберите {LSTEP[step]}",
                              call.message.chat.id,
                              call.message.message_id,
                              reply_markup=key)
    elif result:
        bot.send_message(call.message.chat.id, f"Дата выезда из отеля: {result}")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        with bot.retrieve_data(call.message.chat.id) as data:
            data['checkOutDate'] = result
        bot.set_state(call.message.chat.id, state=models.UserInputState.num_of_adult)
        bot.send_message(call.message.chat.id, "Введите количество совершеннолетних:")


@bot.message_handler(state=models.UserInputState.num_of_adult)  # +
def num_of_adult(message: Message) -> None:
    logger.info('Ввод и запись количества взрослых клиентов: ' + message.text)
    if message.text.isdigit():
        with bot.retrieve_data(message.chat.id) as data:
            data['num_of_adult'] = int(message.text)
        models.show_buttons_photo_need_yes_no(message)
        # bot.set_state(message.chat.id, models.UserInputState.landmarkIn)
        # bot.send_message(message.chat.id, 'Введите начало диапазона расстояния от центра (в милях).')
    else:
        bot.send_message(message.chat.id, 'Ошибка! Вы ввели не число! Повторите ввод!')


@bot.callback_query_handler(func=lambda call: call.data.isalpha())
def need_photo_callback(call: CallbackQuery) -> None:
    if call.data == 'yes':
        logger.info('Нажата кнопка "ДА"')
        with bot.retrieve_data(call.message.chat.id) as data:
            data['photo_need'] = call.data
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.set_state(call.message.chat.id, models.UserInputState.photo_count)
        bot.send_message(call.message.chat.id, 'Сколько вывести фотографий? От 1 до 10!')
    elif call.data == 'no':
        logger.info('Нажата кнопка "НЕТ"')
        with bot.retrieve_data(call.message.chat.id) as data:
            data['photo_need'] = call.data
            data['photo_count'] = '0'


@bot.message_handler(state=models.UserInputState.photo_count)
def input_photo_quantity(message: Message) -> None:
    if message.text.isdigit():
        if 0 < int(message.text) <= 10:
            logger.info('Ввод и запись количества фотографий: ' + message.text)
            with bot.retrieve_data(message.chat.id) as data:
                data['photo_count'] = message.text
            bot.set_state(message.chat.id, models.UserInputState.landmarkIn)
            bot.send_message(message.chat.id, 'Введите начало диапазона расстояния от центра (в милях).')
        else:
            bot.send_message(message.chat.id, 'Число фотографий должно быть в диапазоне от 1 до 10! Повторите ввод!')
    else:
        bot.send_message(message.chat.id, 'Ошибка! Вы ввели не число! Повторите ввод!')



@bot.message_handler(state=models.UserInputState.landmarkIn)  # +
def input_landmark_in(message: Message):
    if message.text.isdigit():
        with bot.retrieve_data(message.chat.id) as data:
            data['landmark_in'] = message.text
            bot.set_state(message.chat.id, models.UserInputState.landmarkIn)
        bot.set_state(message.chat.id, models.UserInputState.landmarkOut)
        bot.send_message(message.chat.id, 'Введите конец диапазона расстояния от центра (в милях).')
    else:
        bot.send_message(message.chat.id, 'Ошибка! Вы ввели не число! Повторите ввод!')


@bot.message_handler(state=models.UserInputState.landmarkOut)  # +
def input_landmark_out(message: Message):
    if message.text.isdigit():
        with bot.retrieve_data(message.chat.id) as data:
            data['landmark_out'] = message.text
            print_data(message, data)
            find_and_show_hotels(message, data)
    else:
        bot.send_message(message.chat.id, 'Ошибка! Вы ввели не число! Повторите ввод!')


def print_data(message: Message, data: Dict):  # +
    logger.info('Вывод суммарной информации о параметрах запроса пользователем.')
    database.add_query(data)
    text_message = ('Исходные данные:\n'
                    f'Дата и время запроса: {data["date_time"]}\n'
                    f'Введена команда: {data["command"]}\n'
                    f'Вы ввели город: {data["input_city"]}\n'
                    f'Выбран город с id: {data["destination_id"]}\n'
                    f'Количество отелей: {data["quantity_hotels"]}\n'
                    f'Минимальный ценник: {data["price_min"]}\n'
                    f'Максимальный ценник: {data["price_max"]}\n'
                    f'Дата заезда: {data["checkInDate"]}\n'
                    f'Дата выезда: {data["checkOutDate"]}\n')
    with open('log.txt', 'a', encoding='utf-8') as log:
        log.write(text_message + '\n')
    if data['sort'] == 'DISTANCE':
        bot.send_message(message.chat.id, text_message +
                         f'Начало диапазона от центра: {data["landmark_in"]}\n'
                         f'Конец диапазона от центра: {data["landmark_out"]}')
    else:
        bot.send_message(message.chat.id, text_message)


def find_and_show_hotels(message: Message, data: Dict) -> None:
    url = "https://hotels4.p.rapidapi.com/properties/v2/list"
    payload = {
        "currency": "USD",
        "eapid": 1,
        "locale": "en_US",
        "siteId": 300000001,
        "destination": {"regionId": data['destination_id']},
        "checkInDate": {
            'day': int(data['checkInDate'].day),
            'month': int(data['checkInDate'].month),
            'year': int(data['checkInDate'].year),
        },
        "checkOutDate": {
            'day': int(data['checkOutDate'].day),
            'month': int(data['checkOutDate'].month),
            'year': int(data['checkOutDate'].year),
        },
        "rooms": [
            {
                "adults": int(data['num_of_adult']),
                "children": [{"age": 5}, {"age": 7}]
            }
        ],
        "resultsStartingIndex": 0,
        "resultsSize": 30,
        "sort": data['sort'],
        "filters": {"price": {
            "max": int(data['price_max']),
            "min": int(data['price_min'])
        }}
    }
    response_hotels = requests.post(url, json=payload, headers=headers)
    logger.info(f'Сервер вернул ответ {response_hotels.status_code}')
    if response_hotels.status_code == 200:
        hotels = models.get_hotels(response_hotels.text, data['command'], data["landmark_in"], data["landmark_out"])
        if 'error' in hotels:
            bot.send_message(message.chat.id, hotels['error'])
            bot.send_message(message.chat.id, 'Попробуйте осуществить поиск с другими параметрами')

        count = 0
        for hotel in hotels.values():
            if count < int(data['quantity_hotels']):
                count += 1
                summary_payload = {
                    "currency": "USD",
                    "eapid": 1,
                    "locale": "en_US",
                    "siteId": 300000001,
                    "propertyId": str(hotel['id'])
                }
                summary_url = "https://hotels4.p.rapidapi.com/properties/v2/detail"
                get_summary = settings.gen_request('POST', summary_url, summary_payload)
                logger.info(f'Сервер вернул ответ {get_summary.status_code}')
                if get_summary.status_code == 200:
                    summary_info = models.hotel_info(get_summary.text)

                    caption = f'Название: {hotel["name"]}\n ' \
                              f'Адрес: {summary_info["address"]}\n' \
                              f'Стоимость проживания в сутки: {round(hotel["price"], 2)}\n ' \
                              f'Расстояние до центра: {round(hotel["distance"], 2)} mile.\n'
                    medias = []
                    links_to_images = []
                    # сформируем рандомный список из ссылок на фотографии, ибо фоток много, а надо только 10
                    try:
                        for random_url in range(int(data['photo_count'])):
                            links_to_images.append(summary_info['images']
                                                   [random.randint(0, len(summary_info['images']) - 1)])
                    except IndexError:
                        continue

                    # Не важно, нужны пользователю фотографии или нет ссылки на них мы передаем в функцию
                    # для сохранения в базе данных
                    data_to_db = {hotel['id']: {'name': hotel['name'], 'address': summary_info['address'],
                                                'price': hotel['price'], 'distance': round(hotel["distance"], 2),
                                                'date_time': data['date_time'], 'images': links_to_images}}
                    database.add_response(data_to_db)
                    # Если количество фотографий > 0: создаем медиа группу с фотками и выводим ее в чат
                    if int(data['photo_count']) > 0:
                        # формируем MediaGroup с фотографиями и описанием отеля и посылаем в чат
                        for number, url in enumerate(links_to_images):
                            if number == 0:
                                medias.append(InputMediaPhoto(media=url, caption=caption))
                            else:
                                medias.append(InputMediaPhoto(media=url))
                        logger.info("Выдаю найденную информацию в чат")
                        bot.send_media_group(message.chat.id, medias)
                    else:
                        # если фотки не нужны, то просто выводим данные об отеле
                        logger.info("Выдаю найденную информацию в чат")
                        bot.send_message(message.chat.id, caption)
                else:
                    bot.send_message(message.chat.id, f'Что-то пошло не так, код ошибки: {get_summary.status_code}')
            else:
                break
    else:
        bot.send_message(message.chat.id, f'Что-то пошло не так, код ошибки: {response_hotels.status_code}')
    bot.send_message(message.chat.id, 'Поиск окончен!')


def check_command(command: str):
    if command == '/bestdeal':
        return 'DISTANCE'
    elif command == '/lowprice' or command == '/highprice':
        return 'PRICE_LOW_TO_HIGH'



if __name__ == '__main__':
    bot.add_custom_filter(StateFilter(bot))
    set_default_commands(bot)
    bot.infinity_polling()
