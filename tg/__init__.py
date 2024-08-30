# tg/__init__.py
import os
import glob

# Получаем путь к текущей директории
current_dir = os.path.dirname(__file__)

# Получаем список всех файлов Python в текущей директории, кроме __init__.py
modules = glob.glob(os.path.join(current_dir, '*.py'))

# Список для хранения названий модулей
keys = []

# Добавляем все файлы Python, кроме __init__.py, в список модулей
for module in modules:
    if not module.endswith('__init__.py'):
        keys.append(os.path.basename(module)[:-3])  # Удаляем .py

# Импортируем модули
for module_name in keys:
    __import__(module_name, globals(), locals(), level=1)

# Определяем __all__ для управления экспортом
__all__ = keys
