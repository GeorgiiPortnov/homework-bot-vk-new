import logging
import os
import random
import sys
import time

import requests
import vk_api
from dotenv import load_dotenv
from exceptions import ApiConnectionError, ApiResponseError
from http import HTTPStatus

HTTPStatus.OK

load_dotenv()

VK_TOKEN = os.getenv('VK_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
VK_USER_ID = os.getenv('VK_USER_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {
    'Authorization': f'OAuth {PRACTICUM_TOKEN}'
}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность обязательных переменных окружения."""
    missing_keys = []
    tockens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'VK_TOKEN': VK_TOKEN,
        'VK_USER_ID': VK_USER_ID
    }

    for key, value in tockens.items():
        if not value or not str(value).strip():
            missing_keys.append(key)
    return missing_keys


def send_message(vk, message):
    """Отправляет сообщение в VK пользователю VK_USER_ID."""
    try:
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=random.randint(0, 2**31 - 1)
        )
        logger.debug('Удачная отправка сообщения в VK')
    except Exception as error:
        logger.error('Сбой при отправке сообщения: %s', error)


def get_api_answer(timestamp):
    """Запрашивает статусы домашних работ у API Практикум Домашка."""
    params = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=5
        )
        if response.status_code != HTTPStatus.OK:
            raise ApiResponseError(
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа: {response.status_code}'
            )
        return response.json()
    except requests.exceptions.RequestException as error:
        raise ApiConnectionError('Сбой соединения с API') from error


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')

    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ homeworks')

    if not isinstance(response['homeworks'], list):
        raise TypeError('Ключ homeworks не является списком')


def parse_status(homework):
    """Извлекает статус домашней работы и формирует сообщение."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('В ответе API отсутствует ключ homework_name')

    homework_status = homework.get('status')
    if homework_status is None:
        raise ValueError('В ответе API отсутствует ключ status')

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]
    return (
        f'Изменился статус проверки работы "{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    missing = check_tokens()
    if missing:
        logger.critical(
            'Нет обязательных переменных окружения: %s при запуске бота',
            ', '.join(missing)
        )
        raise RuntimeError('Критическая ошибка: не заданы токены')

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()

    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)

            homeworks = response.get('homeworks', [])
            if not homeworks:
                logger.debug('Новых статусов нет')
            else:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(vk, message)

            timestamp = int(time.time())

        except ApiResponseError as error:
            logger.error('Ошибка ответа API: %s', error)

        except ApiConnectionError as error:
            logger.error('Сбой при подключении к API: %s', error)

        except Exception as error:
            logger.error('Сбой в работе программы: %s', error)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
