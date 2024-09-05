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
    if pool is None or not proxies:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    async with pool.acquire() as conn:
        async with conn.transaction():
            for proxy in proxies:
                if proxy.get('link', None) is None or proxy.get('version', None) == 'local':
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

async def generate_ipv6(mask):
    network = ipaddress.IPv6Network(mask)
    network_address = int(network.network_address)
    num_addresses = network.num_addresses
    random_offset = random.randint(0, num_addresses - 1)
    random_ipv6_address = str(ipaddress.IPv6Address(network_address + random_offset))
    await manage_ipv6_address(random_ipv6_address)
    return random_ipv6_address

async def manage_ipv6_address(ip_addr, interface='ens3', only_del=False):
    current_platform = platform.system()
    succeed = False

    async def execute_command(command):
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.info(f"Command failed: {stderr.decode().strip()}")

    if current_platform == 'Linux':
        if only_del:
            await execute_command(f"sudo ip -6 addr del {ip_addr} dev {interface} || true")
        await execute_command(f"sudo ip -6 addr add {ip_addr} dev {interface}")
        succeed = True

    elif current_platform == 'Windows':
        if only_del:
            await execute_command(f"netsh interface ipv6 delete address \"{interface}\" {ip_addr}")
        await execute_command(f"netsh interface ipv6 add address \"{interface}\" {ip_addr}")
        succeed = True
    else:
        logger.info(f"Unsupported platform: {current_platform}")

    if succeed:
        # Adjust or remove sleep as per your need
        await asyncio.sleep(0.5)  # Reduced sleep for faster execution


def ensure_sysctl_config(file_path, configs):
    if platform.system() != 'Linux':
        return

    try:
        # Read the existing configuration file
        already = {}
        with open(file_path, 'r') as file:
            existing_lines = file.readlines()
            for line in existing_lines:
                # Skip comments and empty lines
                stripped_line = line.strip()
                if stripped_line.startswith('#') or not stripped_line:
                    continue
                
                # Safely split lines by '=', handling cases with comments
                if '=' in stripped_line:
                    key, value = stripped_line.split('=', 1)
                    already[key.strip()] = value.split('#', 1)[0].strip()  # Split off any comments after '#'

        # Update or add missing configurations
        modified = False
        for key, value in configs.items():
            if key not in already or already[key] != value:
                already[key] = value
                modified = True

        # If modifications were made, write back to the file
        if modified:
            with open(file_path, 'w') as file:
                for key, value in already.items():
                    config_line = f"{key} = {value}\n"
                    file.write(config_line)
                    logger.info(f"Updating or adding configuration: {config_line.strip()}")

            # Apply the new configurations
            os.system("sysctl -p")
            logger.info("Configuration applied successfully.")
        else:
            logger.info("No configuration changes needed.")
    
    except IOError as e:
        logger.error(f"Error reading or writing the file: {e}")

async def remove_ipv6_address(ip, interface, semaphore):
    async with semaphore:
        # Удаляем IPv6 адрес
        process = await asyncio.create_subprocess_shell(
            f"sudo ip -6 addr del {ip} dev {interface}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.debug(f"Successfully removed IPv6 address: {ip}")
        else:
            logger.error(f"Failed to remove IPv6 address {ip}: {stderr.decode().strip()}")

async def clear_ipv6_interface(interface='ens3', mask=128):
    semaphore = asyncio.Semaphore(8)

    try:
        # Получаем список всех IPv6 адресов на интерфейсе
        proc = await asyncio.create_subprocess_shell(
            f"ip -6 addr show dev {interface}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"Error fetching IPv6 addresses: {stderr.decode().strip()}")
            return

        # Извлекаем адреса с маской /128
        ipv6_addresses = [
            line.split()[1]
            for line in stdout.decode().splitlines()
            if f'/{mask}' in line
        ]

        if not ipv6_addresses:
            logger.info(f"No IPv6 addresses with /{mask} mask found on {interface}.")
            return

        # Запускаем удаление адресов с ограничением на количество одновременно выполняемых задач
        tasks = [remove_ipv6_address(ip, interface, semaphore) for ip in ipv6_addresses]
        await asyncio.gather(*tasks)

        logger.info(f"Successfully removed IPv6 addresses from interface {interface}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    
    finally:
        await delete_all_proxy_by_v(v='ipv6')


async def prepare():
    # Sysctl configurations to ensure
    sysctl_configs = {
        "net.ipv6.conf.ens3.proxy_ndp": "1",
        "net.ipv6.conf.all.proxy_ndp": "1",
        "net.ipv6.conf.default.forwarding": "1",
        "net.ipv6.conf.all.forwarding": "1",
        "net.ipv6.neigh.default.gc_thresh3": "102400",
        "net.ipv6.route.max_size": "409600",
    }

    # Path to sysctl.conf
    sysctl_conf_file = '/etc/sysctl.conf'

    # Ensure sysctl configurations are set
    ensure_sysctl_config(sysctl_conf_file, sysctl_configs)

    # Clear existing IPv6 addresses on the interface
    await clear_ipv6_interface()

    # Semaphore for limiting concurrent tasks
    sema = asyncio.Semaphore(4)

    # Assuming ipv6_mask and ipv6_count are defined elsewhere
    tasks = []
    if ipv6_mask and not is_local_address(ipv6_mask):
        async with sema:
            for _ in range(ipv6_count * 3 // 2):
                task = asyncio.create_task(generate_ipv6(ipv6_mask), name=f'ipv6_gen{_}')
                tasks.append(task)

            # Track task completion
            while any(not t.done() for t in tasks):
                completed_tasks = sum(1 for t in tasks if t.done())
                logger.info(f'Addresses added: {completed_tasks}/{ipv6_count} ({ipv6_count * 3 // 2})')
                await asyncio.sleep(1)

    # Apply proxy settings once all tasks are done
    proxies = {}
    for t in tasks:
        link = t.result()
        proxies[link] = False
    await set_proxy(proxies, v='ipv6')
