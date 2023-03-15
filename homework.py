import logging
import os
import sys
import time

import exceptions
import json
import requests
import telegram

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

ENV_VARS = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
FROM_DATE = 1675719091


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия токена в ENV."""
    # return all(ENV_VARS)  # ????????????????????? так не работает -
    # 'Убедитесь, что при запуске бота без переменных окружения '
    # 'программа принудительно останавливается.'
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logger.info('Начало отправки сообщения')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        error_message = (
            f'Ошибка при отправке сообщения в чат: {error}'
        )
        logger.error(error_message)
        raise exceptions.SendMessageError(error_message)
    else:
        logging.debug(
            f'Сообщение Успешно отправлено в чат: {message}'
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
        error_message = (
            f'Ошибка при запросе к API: {error}'
        )
        raise exceptions.BadHttpStatus(error_message)
    status_code = homework_statuses.status_code
    if status_code != HTTPStatus.OK:
        error_message = (
            f'{ENDPOINT} - недоступен. Код ответа API: {status_code}'
        )
        raise exceptions.BadHttpStatus(error_message)
    try:
        response = homework_statuses.json()
    except json.JSONDecodeError as error:
        json_error_message = (
            f'данные не являются допустимым форматом JSON: {error}'
        )
        logger.error(json_error_message)
    return response


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            f'ответ сервиса не словарь. {response}'
        )
    homeworks = response.get('homeworks')
    if 'homeworks' not in response:
        raise KeyError(
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
        error_message = (
            'неожиданный статус домашней работы, обнаруженный в ответе API'
        )
        raise exceptions.UnknownHomeworkStatus(error_message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = 'Отсутствуют переменные окружения'
        logger.critical(error_message)
        sys.exit('Отсутствуют переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_verdict = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date', int(time.time()))
            if len(homeworks) > 0:
                verdict = parse_status(homeworks[0])
                send_message(bot, verdict)
                prev_verdict = verdict
                logger.info('Получен статус')
            else:
                status_message = 'Статус не обновлен'
                logger.debug(status_message)
                send_message(bot, status_message)
                prev_verdict = status_message
                logger.info(status_message)
        except Exception as error:
            error_message = f'Сбой в работе бота: {error}'
            logger.error(error_message)
            if error_message != prev_verdict:
                send_message(bot, error_message)
                prev_verdict = error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        filename='main.log',
        format='%(asctime)s [%(levelname)s] %(funcName)s,'
        'Line-%(lineno)s, message-%(message)s',
        filemode='w',
        encoding='UTF-8'
    )
    main()
