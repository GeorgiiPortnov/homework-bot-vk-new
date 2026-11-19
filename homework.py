import logging
import os
import random
import sys
import time

import requests
import vk_api
from dotenv import load_dotenv

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
    if (
        VK_TOKEN is not None
        and PRACTICUM_TOKEN is not None
        and PRACTICUM_TOKEN.strip()
        and VK_USER_ID is not None
    ):
        return True
    else:
        logger.critical(
            'Отсутствие обязательных переменных окружения '
            'во время запуска бота'
        )
        return False


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
        logger.error(f'Сбой при отправке сообщения: {error}')


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
        if response.status_code != 200:
            raise requests.exceptions.HTTPError(
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа: {response.status_code}'
            )
        return response.json()
    except requests.exceptions.RequestException as error:
        logger.error(f'Сбой при запросе к API: {error}')
        raise ConnectionError('Ошибка при запросе к API') from error


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
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit('Отсутствуют переменные окружения')

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

        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
