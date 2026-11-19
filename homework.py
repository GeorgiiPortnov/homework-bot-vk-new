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
    vk_token = os.getenv('VK_TOKEN')
    practicum_token = os.getenv('PRACTICUM_TOKEN')
    vk_user_id = os.getenv('VK_USER_ID')

    if (
        vk_token is not None
        and practicum_token is not None
        and practicum_token.strip()
        and vk_user_id is not None
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
    headers = {'Authorization': f'Bearer {PRACTICUM_TOKEN}'}
    params = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT,
            headers=headers,
            params=params,
            timeout=5,
        )
        if response.status_code != 200:
            logger.error(
                f'Недоступность эндпоинта: {ENDPOINT}. '
                f'Код ответа API: {response.status_code}'
            )
            return None

        return response.json()
    except requests.exceptions.RequestException as error:
        logger.error(f'Сбой при запросе к API: {error}')
        return None


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарем')
        return False

    missing_keys = []
    for key in ('homeworks',):
        if key not in response:
            missing_keys.append(key)

    if missing_keys:
        logger.error(
            'Нет ожидаемых ключей в ответе API: '
            f'{", ".join(missing_keys)}'
        )
        return False

    if not isinstance(response['homeworks'], list):
        logger.error('Ключ homeworks не является списком')
        return False

    return True


def parse_status(homework):
    """Извлекает статус домашней работы и формирует сообщение."""
    if not isinstance(homework, dict):
        logger.error('Объект не является словарем')
        return 'Некорректные данные о домашней работе'

    homework_status = homework.get('status')
    if homework_status is None:
        logger.error(f'Нет статуса: {homework_status}')
        return 'Статус не найден'

    if homework_status in HOMEWORK_VERDICTS:
        homework_name = homework.get('homework_name', 'Домашняя работа')
        verdict = HOMEWORK_VERDICTS[homework_status]
        return (
            f'Изменился статус проверки работы "{homework_name}". '
            f'{verdict}'
        )
    else:
        logger.critical(
            f'Неожиданный статус домашней работы: {homework_status}'
        )
        return f'Ошибка: неизвестный статус работы — {homework_status}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    # Создаем сессию для бота
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            if response is None:
                logger.warning(
                    'Ответ от API отсутствует, '
                    'повтор через RETRY_PERIOD'
                )

            elif not check_response(response):
                logger.warning('Некорректный формат ответа API')

            else:
                homeworks = response.get('homeworks', [])

                if not homeworks:
                    logger.debug('Новых статусов нет')
                else:
                    for homework in homeworks:
                        message = parse_status(homework)
                        send_message(vk, message)
                timestamp = int(time.time())

        except Exception as error:
            logger.critical(f'Критический сбой в main: {error}')

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
