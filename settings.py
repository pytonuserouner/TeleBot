import keys
import requests
# from dotenv import load_dotenv, find_dotenv

# if not find_dotenv():
#     exit('Переменные окружения не загружены т.к отсутствует файл .env')
# else:
#     load_dotenv()

# BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_TOKEN = keys.BOT_TOKEN
# RAPID_API_KEY = os.getenv('RAPID_API_KEY')
RAPID_API_KEY = keys.RAPID_API_KEY
DEFAULT_COMMANDS = (
    ('start', "Запустить бота"),
    ('help', "Помощь по командам бота"),
    ('lowprice', "Вывод самых дешёвых отелей в городе"),
    ('highprice', "Вывод самых дорогих отелей в городе"),
    ('bestdeal', "вывод отелей, наиболее подходящих по цене и расположению от центра"),
    ('history', "Вывод истории поиска отелей из БД"),
    ('simple_history', "Вывод истории поиска отелей из файла"),

)

headers = {
    "content-type": "application/json",
    "X-RapidAPI-Key": RAPID_API_KEY,
    "X-RapidAPI-Host": "hotels4.p.rapidapi.com",
}


def gen_request(method: str, url: str, query_string: dict) -> requests.Response:
    if method == "GET":
        response_get = requests.request("GET", url, params=query_string, headers=headers)
        return response_get
    elif method == "POST":
        response_post = requests.request("POST", url, json=query_string, headers=headers)
        return response_post
