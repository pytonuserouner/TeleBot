import json
import telebot
from loguru import logger
from telebot.handler_backends import State, StatesGroup
from telebot.types import Message, Dict
from telebot import types, StateMemoryStorage
import settings

storage = StateMemoryStorage()
bot = telebot.TeleBot(token=settings.BOT_TOKEN, state_storage=storage)


class UserInputState(StatesGroup):
    command = State()  # команда, которую выбрал пользователь
    input_city = State()  # город, который ввел пользователь
    destinationId = State()  # запись id города
    quantity_hotels = State()  # количество отелей, нужное пользователю
    priceMin = State()  # минимальная стоимость отеля
    priceMax = State()  # максимальная стоимость отеля
    start_date = State()
    end_date = State()
    input_date = State()
    checkDate = State()
    checkInDate = State()  # дата заселения
    checkOutDate = State()  # дата выезда
    num_of_adult = State()  # количество взрослых
    num_of_child = State()  # количество детей
    landmarkIn = State()  # начало диапазона расстояния от центра
    landmarkOut = State()  # конец диапазона расстояния от центра
    photo_count = State()  # количество фотографий
    history_select = State()  # выбор истории поиска


def show_cities_buttons(message: Message, possible_cities: Dict): # +
    keyboards_cities = types.InlineKeyboardMarkup()
    for key, value in possible_cities.items():
        keyboards_cities.add(types.InlineKeyboardButton(text=value["regionNames"], callback_data=value["gaiaId"]))
    bot.send_message(message.from_user.id, "Пожалуйста, выберите город", reply_markup=keyboards_cities)


def get_city(response_text: str) -> Dict: # +
    possible_cities = {}
    data = json.loads(response_text)
    if not data:
        raise LookupError('Запрос пуст...')
    for id_place in data['sr']:
        try:
            possible_cities[id_place['gaiaId']] = {
                "gaiaId": id_place['gaiaId'],
                "regionNames": id_place['regionNames']['fullName']
            }
        except KeyError:
            continue
    return possible_cities



def get_hotels(response_text: str, command: str, landmark_in: str, landmark_out: str):
    data = json.loads(response_text)
    if not data:
        raise LookupError('Запрос пуст...')
    if 'errors' in data.keys():
        return {'error': data['errors'][0]['message']}

    hotels_data = {}
    for hotel in data['data']['propertySearch']['properties']:
        try:
            hotels_data[hotel['id']] = {
                'name': hotel['name'], 'id': hotel['id'],
                'distance': hotel['destinationInfo']['distanceFromDestination']['value'],
                'unit': hotel['destinationInfo']['distanceFromDestination']['unit'],
                'price': hotel['price']['lead']['amount']
            }
        except (KeyError, TypeError):
            continue
    if command == '/highprice':
        hotels_data = {
            key: value for key, value in
            sorted(hotels_data.items(), key=lambda hotel_id: hotel_id[1]['price'], reverse=True)
        }
    # Обнуляем созданный ранее словарь и добавляем туда только те отели, которые соответствуют диапазону.
    elif command == '/bestdeal':
        hotels_data = {}
        for hotel in data['data']['propertySearch']["properties"]:
            if float(landmark_in) < hotel['destinationInfo']['distanceFromDestination']['value'] < float(landmark_out):
                hotels_data[hotel['id']] = {
                    'name': hotel['name'], 'id': hotel['id'],
                    'distance': hotel['destinationInfo']['distanceFromDestination']['value'],
                    'unit': hotel['destinationInfo']['distanceFromDestination']['unit'],
                    'price': hotel['price']['lead']['amount']
                }
    return hotels_data


def hotel_info(hotels_request: str):
    data = json.loads(hotels_request)
    if not data:
        raise LookupError('Запрос пуст...')
    hotel_data = {
        'id': data['data']['propertyInfo']['summary']['id'], 'name': data['data']['propertyInfo']['summary']['name'],
        'address': data['data']['propertyInfo']['summary']['location']['address']['addressLine'],
        'coordinates': data['data']['propertyInfo']['summary']['location']['coordinates'],
        'images': [
            url['image']['url'] for url in data['data']['propertyInfo']['propertyGallery']['images']

        ]
    }
    return hotel_data


def show_buttons_photo_need_yes_no(message: Message) -> None:
    logger.info('Вывод кнопок о необходимости фотографий')
    keyboard_yes_no = types.InlineKeyboardMarkup()
    keyboard_yes_no.add(types.InlineKeyboardButton(text='ДА', callback_data='yes'))
    keyboard_yes_no.add(types.InlineKeyboardButton(text='НЕТ', callback_data='no'))
    bot.send_message(message.chat.id, "Нужно вывести фотографии?", reply_markup=keyboard_yes_no)





