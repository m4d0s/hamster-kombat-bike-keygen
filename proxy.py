import socket
import psutil
import json
from database import get_pool, SCHEMAS, now, POOL

json_config = json.loads(open('config.json').read())

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

def get_ipv6_addresses():
    ipv6_addresses = []
    interfaces = psutil.net_if_addrs()
    i = 0
    for interface, addrs in interfaces.items():
        for addr in addrs:
            if addr.family == socket.AF_INET6 and not is_local_address(addr.address): 
                ipv6_addresses.append([i, addr.address, interface, 8080])
                i += 1
    id = int(input('Enter port (8080 by default, 0 to disable): '))
    if id and id != 0:
        ipv6_addresses[0][3] = id
    else:
        id = 0
    return ipv6_addresses[0] if i > 0 and id != 0 else None

ipv6_address = None

async def get_proxies(pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    proxies = {}

    async with pool.acquire() as conn:
        async with conn.transaction():
            proxy_rows = await conn.fetch(f'SELECT id, proxy, work FROM "{SCHEMAS["CONFIG"]}".proxy')
            proxies = {
                row['proxy']: row['work']
                for row in proxy_rows
            }

    return proxies

async def set_proxy(proxies:dict, pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан

    async with pool.acquire() as conn:
        async with conn.transaction():
            for proxy in proxies:
                await conn.execute(f'''
                    INSERT INTO "{SCHEMAS["CONFIG"]}".proxy (link, work, time)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (link) DO UPDATE
                    SET work = EXCLUDED.work, time = EXCLUDED.time
                ''', proxy, proxies[proxy], now())       

async def get_free_proxy(pool=POOL):
    if pool is None:
        pool = await get_pool()  # Получаем пул соединений, если он не был передан
    
    if json_config['IPV6']:
        global ipv6_address
        ipv6_address = ipv6_address or get_ipv6_addresses()
        if ipv6_address:
            return {'link': f'https://[{ipv6_address[1]}]:{ipv6_address[3]}', 'work': False, 'version': 'ipv6'}
        

    async with pool.acquire() as conn:
        async with conn.transaction():
            proxy = await conn.fetchrow(f'''
                SELECT link, work FROM "{SCHEMAS["CONFIG"]}".proxy
                WHERE work = false LIMIT 1
            ''')

            if not proxy:
                proxy = await conn.fetchrow(f'''
                    SELECT link, work FROM "{SCHEMAS["CONFIG"]}".proxy
                    ORDER BY RANDOM() LIMIT 1
                ''')

            if proxy:
                await set_proxy({proxy['link']: True}, pool=pool)

    return {'link': proxy['link'], 'work': proxy['work'], 'version': 'ipv4'} if proxy else None