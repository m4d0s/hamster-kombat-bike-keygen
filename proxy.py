import socket
import psutil
import ipaddress
import random
import json
from database import get_pool, SCHEMAS, now, POOL

json_config = json.loads(open('config.json').read())

def is_local_address(ipv6_address):
    if not ipv6_address:
        return False
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
    if not is_local_address(json_config.get('IPV6', None)):
        return [0, json_config['IPV6'], 'Custom ipv6', 8080]
    for interface, addrs in interfaces.items():
        for addr in addrs:
            if addr.family == socket.AF_INET6 and not is_local_address(addr.address): 
                ipv6_addresses.append([i, addr.address, interface, 8080])
                i += 1
    if not ipv6_addresses:
        raise RuntimeError("No valid IPv6 addresses found")
    id = json_config.get('IPV6_PORT', 0)
    ipv6_addresses[0][3] = id
    return ipv6_addresses[0]

def generate_alternative_ipv6():
    ipv6_address = get_ipv6_addresses()
    
    # Parse the current IPv6 address
    address = ipaddress.IPv6Address(ipv6_address[1])
    
    # Get the network prefix (first 64 bits) and the current interface ID (last 64 bits)
    network_prefix = address.packed[:8]  # First 8 bytes (64 bits)
    current_interface_id = address.packed[8:]  # Last 8 bytes (64 bits)
    
    # Generate a random interface ID
    new_interface_id = random.getrandbits(64).to_bytes(8, byteorder='big')
    
    # Create a new IPv6 address
    new_address = ipaddress.IPv6Address(network_prefix + new_interface_id)
    
    ipv6_address[1] = str(new_address)
    
    # Log and validate the new address
    # print(f"Generated IPv6 Address: {ipv6_address[1]}")
    
    return ipv6_address

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
    
    if json_config['IPV6_PORT'] > 0:
        ipv6_address = generate_alternative_ipv6()
        if ipv6_address and ipv6_address[3] != 0:
            return {'link': f'http://[{ipv6_address[1]}]:{ipv6_address[3]}', 'work': False, 'version': 'ipv6'}
        

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