class ApiConnectionError(Exception):
    """Сбой при подключении к API Практикум Домашка."""

class ApiResponseError(Exception):
    """Некорректный ответ от API Практикум Домашка."""

class ConfigError(Exception):
    """Критическая ошибка конфигурации: отсутствуют токены"""
