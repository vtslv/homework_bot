import logging
import os
import sys
import time

import exceptions
import requests
import telegram

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

ENV_VARS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
FROM_DATE = 1675719091


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s [%(levelname)s] %(funcName)s,'
    'Line-%(lineno)s, message-%(message)s',
    filemode='w',
    encoding='UTF-8'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия токена в ENV."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(
            f'Сообщение отправлено в чат: {message}'
        )
    except telegram.error.TelegramError as error:
        logging.error(
            f'Ошибка при отправке сообщения в чат: {error}'
        )
        raise exceptions.SendMessageError(
            f'Ошибка при отправке сообщения в чат: {error}'
        )


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as error:
        logging.error(
            f'Ошибка при запросе к API: {error}'
        )
        raise exceptions.BadHttpStatus(
            f'Ошибка при запросе к API: {error}'
        )
    status_code = homework_statuses.status_code
    if status_code != HTTPStatus.OK:
        logging.error(
            f'{ENDPOINT} - недоступен. Код ответа API: {status_code}'
        )
        raise exceptions.BadHttpStatus(
            f'{ENDPOINT} - недоступен. Код ответа API: {status_code}'
        )
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            f'ответ сервиса не словарь. {response}'
        )
    try:
        homeworks = response['homeworks']
    except KeyError:
        logging.error(
            'Ошибка ключа: нет "homeworks"'
        )
    if not isinstance(homeworks, list):
        raise TypeError(
            'ответ сервиса по ключу homeworks не список'
        )
    return homeworks


def parse_status(homework):
    """Проверка статуса HW."""
    if 'homework_name' not in homework:
        raise KeyError(
            'Отсутствует ключ "homework_name" в ответе API'
        )
    if 'status' not in homework:
        raise KeyError(
            'Отсутствует ключ "status" в ответе API'
        )
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        logging.error(
            'неожиданный статус домашней работы, обнаруженный в ответе API'
        )
        raise exceptions.UnknownHomeworkStatus(
            'неожиданный статус домашней работы, обнаруженный в ответе API'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not check_tokens():
        er_message = 'Отсутствуют переменные окружения'
        logging.critical(er_message)
        send_message(bot, er_message)
        sys.exit('Отсутствуют переменные окружения')
    current_timestamp = int(time.time())
    prev_verdict = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date', int(time.time()))
            if len(homeworks) == 0:
                logging.debug('Список пуст')
                len_message = 'Список пуст'
                if len_message != prev_verdict:
                    send_message(bot, len_message)
                    prev_verdict = len_message
            verdict = parse_status(homeworks[0])
            if verdict != prev_verdict:
                send_message(bot, verdict)
                prev_verdict = verdict
        except exceptions.SendMessageError as error:
            error_message = (
                f'Ошибка при отправке сообщения: {error}'
            )
            logging.error(error_message)
        except Exception as error:
            er_message = f'Сбой в работе бота: {error}'
            logging.error(er_message)
            if er_message != prev_verdict:
                send_message(bot, er_message)
                prev_verdict = er_message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
