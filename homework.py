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


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handlers = logging.StreamHandler(sys.stdout)
logger.addHandler(handlers)
encode='utf-8'


def check_tokens():
    """Проверка наличия токена в ENV."""
    # return all[ENV_VARS]
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


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
            f'"{ENDPOINT}" - недоступен. Код ответа API: {status_code}'
        )
        raise exceptions.BadHttpStatus(
            f'"{ENDPOINT}" - недоступен. Код ответа API: {status_code}'
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
    if not check_tokens():
        logging.critical('Отсутствуют переменные окружения')
        raise SystemExit('Отсутствуют переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_verdict = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date', int(time.time()))
            if not homeworks:
                logging.debug('Список пуст')
                continue
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
            message = f'Сбой в работе бота: {error}'
            logging.error(message)
            if message != prev_verdict:
                send_message(bot, message)
                prev_verdict = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
