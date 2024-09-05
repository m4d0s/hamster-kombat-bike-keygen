import ipaddress
import platform
import random
import asyncio
import json
import os
import logging
import subprocess
from database import get_pool, SCHEMAS, now, POOL, log_timestamp

def get_logger(file_level=logging.INFO, base_level=logging.DEBUG):
    # Создаем логгер
    # asyncio.get_event_loop().set_debug(config['DEBUG_LOG'])
    logger = logging.getLogger("logger")
    logger.setLevel(base_level)  # Устанавливаем базовый уровень логирования
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Проверяем, есть ли уже обработчики, и если да, удаляем их
    if logger.hasHandlers():
        logger.handlers.clear()

    # Создаем каталог для логов, если он не существует
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Создаем обработчик для записи в файл
    file_handler = logging.FileHandler(f'{log_dir}/{log_timestamp()}.log')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_lvl = logging.DEBUG if config['DEBUG_LOG'] else logging.INFO
    console_handler.setLevel(console_lvl)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.debug("Logger setup sucessfull!\n\tBase log level: %s, Console log level: %s, File log level: %s", 
                 base_level, console_lvl, file_level)

    return logger

config = json.load(open('config.json', 'r', encoding='utf-8'))
ipv6_mask = config['IPV6']
logger = get_logger()
ipv6_count = config['GEN_PROXY']

json_config = json.loads(open('config.json').read())

async def delete_proxy(proxy,pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'DELETE FROM "{SCHEMAS["CONFIG"]}".proxy WHERE link = $1', proxy['link'])
            
async def delete_all_proxy_by_v(v='ipv6', pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'DELETE FROM "{SCHEMAS["CONFIG"]}".proxy WHERE version = $1', v)

async def set_proxy(proxies:dict, pool=POOL, v='ipv4'):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    async with pool.acquire() as conn:
        async with conn.transaction():
            for proxy in proxies:
                await conn.execute(f'''
                    INSERT INTO "{SCHEMAS["CONFIG"]}".proxy (link, work, time, version)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (link) DO UPDATE
                    SET work = EXCLUDED.work, time = EXCLUDED.time, version = EXCLUDED.version
                ''', proxy, proxies[proxy], now(), v)       

async def get_free_proxy(pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан
    version = 'ipv4'
    if ipv6_mask and not is_local_address(ipv6_mask):
        version = 'ipv6'
        

    async with pool.acquire() as conn:
        async with conn.transaction():
            proxy = await conn.fetchrow(f'''
                SELECT link, work FROM "{SCHEMAS["CONFIG"]}".proxy
                WHERE work = false and version = '{version}' LIMIT 1
            ''')

            if not proxy:
                proxy = await conn.fetchrow(f'''
                    SELECT link, work FROM "{SCHEMAS["CONFIG"]}".proxy
                    WHERE version = '{version}' ORDER BY RANDOM() LIMIT 1
                ''')

            if proxy:
                await set_proxy({proxy['link']: True}, pool=pool, v=version)

    return {'link': proxy['link'], 'work': proxy['work'], 'version': version} if proxy else None

def is_local_address(ipv6_address):
    # Проверяем link-local адреса
    if ipv6_address.startswith('fe80::'):
        return True
    # Проверяем loopback адрес
    if ipv6_address == '::1':
        return True
    # Проверяем unique local адреса (ULA)
    if ipv6_address.startswith('fd') or ipv6_address.startswith('fc'):
        return True
    return False

#prepare
async def generate_ipv6(mask):
    network = ipaddress.IPv6Network(mask)
    network_address = int(network.network_address)
    num_addresses = network.num_addresses
    random_offset = random.randint(0, num_addresses - 1)
    random_ipv6_address = str(ipaddress.IPv6Address(network_address + random_offset))
    await manage_ipv6_address(random_ipv6_address)
    return str(random_ipv6_address)

async def manage_ipv6_address(ip_addr, interface = 'ens3', only_del = False):
    current_platform = platform.system()
    succeed = False
    
    def execute_command(command):
        try:
            subprocess.run(command, check=True, shell=True)
        except subprocess.CalledProcessError as e:
            logger.info(f"Command failed: {e}")
    
    if current_platform == 'Linux':
        # Linux команды
        if only_del:
            execute_command(f"sudo ip -6 addr del {ip_addr} dev {interface} || true")
        execute_command(f"sudo ip -6 addr add {ip_addr} dev {interface}")
        succeed = True
    
    elif current_platform == 'Windows':
        # Windows команды
        if only_del:
            execute_command(f"netsh interface ipv6 delete address \"{interface}\" {ip_addr}")
        execute_command(f"netsh interface ipv6 add address \"{interface}\" {ip_addr}")
        succeed = True
    else:
        logger.info(f"Unsupported platform: {current_platform}")
    
    if succeed:
        await asyncio.sleep(2)

def ensure_sysctl_config(file_path, configs):
    if not platform.system() == 'Linux':
        return
    try:
        # Чтение существующего файла конфигурации
        with open(file_path, 'r') as file:
            existing_lines = file.read()
        
        # Открываем файл в режиме добавления
        with open(file_path, 'a') as file:
            for key, value in configs.items():
                # Формируем строку конфигурации
                config_line = f"{key} = {value}\n"
                # Проверяем наличие строки в файле
                if config_line not in existing_lines:
                    logger.info(f"Adding missing configuration: {config_line.strip()}")
                    file.write(config_line)
                    
        # Применение изменений
        os.system("sysctl -p")
        logger.info("Configuration applied successfully.")
    
    except IOError as e:
        logger.info(f"Error reading or writing the file: {e}")

def clear_ipv6_interface(interface='ens3', mask=128):
    try:
        # Получаем список всех IPv6 адресов с маской /128 на интерфейсе
        result = subprocess.run(
            f"ip -6 addr show dev {interface} | grep '/{mask}' | awk '{{print $2}}'",
            shell=True, capture_output=True, text=True
        )
        ipv6_addresses = result.stdout.strip().split('\n')
        
        for ip in ipv6_addresses:
            if ip:
                logger.debug(f"Удаляю IPv6 адрес: {ip} с интерфейса {interface}")
                subprocess.run(f"sudo ip -6 addr del {ip} dev {interface}", shell=True)
    
    except Exception as e:
        logger.info(f"Произошла ошибка: {e}")


async def prepare():
    # Конфигурации для добавления
    sysctl_configs = {
        "net.ipv6.conf.ens3.proxy_ndp": "1",
        "net.ipv6.conf.all.proxy_ndp": "1",
        "net.ipv6.conf.default.forwarding": "1",
        "net.ipv6.conf.all.forwarding": "1",
        "net.ipv6.neigh.default.gc_thresh3": "102400",
        "net.ipv6.route.max_size": "409600",
    }

    # Путь к файлу sysctl.conf
    sysctl_conf_file = '/etc/sysctl.conf'

    # Обеспечить наличие конфигураций
    ensure_sysctl_config(sysctl_conf_file, sysctl_configs)
    clear_ipv6_interface()
    await delete_all_proxy_by_v(v='ipv6')
    if ipv6_mask and not is_local_address(ipv6_mask):
        tasks = [asyncio.create_task(generate_ipv6(ipv6_mask)) for _ in range(ipv6_count)]
        while any(not t.done() for t in tasks):
            logger.info(f'Addresses added: {len([t.done for t in tasks])}/{ipv6_count}')
            await asyncio.sleep(1)
        for t in tasks:
            await set_proxy({t.result():False}, v='ipv6')
