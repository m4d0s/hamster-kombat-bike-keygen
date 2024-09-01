import socket
import psutil
import ipaddress
import platform
import random
import aiohttp
import asyncio
import json
import http.server
import socketserver
import threading
from database import get_pool, SCHEMAS, now, POOL

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
    
    # if json_config['IPV6_PORT'] > 0:
    #     ipv6_address = start_proxy()
    #     if ipv6_address and ipv6_address[3] != 0:
    #         return {'link': f'http://[{ipv6_address[1]}:{ipv6_address[3]}]', #:{ipv6_address[3]}', 
    #                 'work': False,    'version': 'ipv6'}
        

    async with pool.acquire() as conn:
        async with conn.transaction():
            proxy = await conn.fetchrow(f'''
                SELECT link, work FROM "{SCHEMAS["CONFIG"]}".proxy
                WHERE work = false LIMIT 1
            ''')

            if not proxy:
                proxy = await conn.fetchrow(f'''
                    SELECT link, work FROM "{SCHEMAS["CONFIG"]}".proxy
                    WHERE version = 'ipv4' ORDER BY RANDOM() LIMIT 1
                ''')

            if proxy:
                await set_proxy({proxy['link']: True}, pool=pool)

    return {'link': proxy['link'], 'work': proxy['work'], 'version': 'ipv4'} if proxy else None

# class MyHandler(http.server.SimpleHTTPRequestHandler):
#     def do_GET(self):
#         # Простая обработка GET-запросов
#         self.send_response(200)
#         self.send_header("Content-type", "text/plain")
#         self.end_headers()
#         self.wfile.write(b"Hello, world!")

# def start_proxy_server(ipv6_address, port):
#     handler = MyHandler
#     server = socketserver.TCPServer((ipv6_address, port), handler)
#     print(f"Starting proxy server on {ipv6_address}:{port}")
#     server.serve_forever()

# # Запуск прокси-сервера в отдельном потоке
# def run_proxy_server(ipv6_address, port):
#     server_thread = threading.Thread(target=start_proxy_server, args=(ipv6_address, port))
#     server_thread.daemon = True
#     server_thread.start()
#     return server_thread

# async def check_proxy_aiohttp(ipv6_address, port, test_url="https://api.ipify.org"):
#     proxy_url = f"[{ipv6_address}]:{port}"
#     proxy = f"http://[{ipv6_address}]:{port}"

#     async with aiohttp.ClientSession() as session:
#         try:
#             async with session.get(test_url, proxy=proxy, timeout=10) as response:
#                 if response.status == 200:
#                     text = await response.text()
#                     print(f"Proxy {proxy_url} is working. Public IP: {text}")
#                     return True
#                 else:
#                     print(f"Proxy {proxy_url} failed with status code: {response.status}")
#         except (aiohttp.ClientError, asyncio.TimeoutError) as e:
#             print(f"Proxy {proxy_url} failed. Error: {e}")
    
#     return False

# def is_local_address(ipv6_address):
#     if not ipv6_address:
#         return False
#     if ipv6_address.startswith('fe80::') or ipv6_address == '::1':
#         return True
#     if ipv6_address.startswith('fd') or ipv6_address.startswith('fc'):
#         return True
#     return False

# def get_ipv6_addresses():
#     ipv6_addresses = []
#     interfaces = psutil.net_if_addrs()

#     if not is_local_address(json_config.get('IPV6', None)):
#         return [0, json_config['IPV6'], 'Custom ipv6', json_config['IPV6_PORT']]
    
#     i = 0
#     for interface, addrs in interfaces.items():
#         for addr in addrs:
#             if addr.family == socket.AF_INET6 and not is_local_address(addr.address): 
#                 ipv6_addresses.append([i, addr.address, addr.address, json_config['IPV6_PORT']])
#                 i += 1
#     if not ipv6_addresses:
#         raise RuntimeError("No valid IPv6 addresses found")
    
#     ipv6_addresses[0][3] = json_config.get('IPV6_PORT', 8080)
#     return ipv6_addresses[0]

# def generate_alternative_ipv6():
#     ipv6_address = get_ipv6_addresses()
#     if ipv6_address[3] == 0:
#         return ipv6_address
#     address = ipaddress.IPv6Address(ipv6_address[1])
#     network_prefix = address.packed[:8]
#     new_interface_id = random.getrandbits(64).to_bytes(8, byteorder='big')
#     new_address = ipaddress.IPv6Address(network_prefix + new_interface_id)
#     ipv6_address[1] = str(new_address)
#     print(f"Generated IPv6 Address: {ipv6_address[1]}")
#     return ipv6_address

# async def apply_iptables_rule(ipv6_address, port):
#     if platform.system().lower() == 'windows':
#         print(f"Skipping iptables rule application on Windows for IPv6: {ipv6_address}")
#         return

#     try:
#         await asyncio.create_subprocess_exec(
#             'iptables', '-t', 'nat', '-A', 'PREROUTING', '-p', 'tcp',
#             '--dport', str(port), '-j', 'DNAT', '--to-destination', f'[{ipv6_address}]:{port}'
#         )
#         await asyncio.create_subprocess_exec(
#             'ip6tables', '-A', 'INPUT', '-d', ipv6_address, '-j', 'ACCEPT'
#         )
#         print(f"iptables rule applied for IPv6: {ipv6_address}")
#     except Exception as e:
#         print(f"Failed to apply iptables rule: {e}")
#         raise

# async def start_proxy():
#     ipv6_info = generate_alternative_ipv6()
#     if ipv6_info[3] == 0:
#         return None
#     await apply_iptables_rule(ipv6_info[1], ipv6_info[3])
#     return ipv6_info


# async def main():
#     ipv6_address = await start_proxy()

#     # Запускаем прокси сервер
#     run_proxy_server('::', ipv6_address[3])

#     # Даем серверу немного времени, чтобы запуститься
#     await asyncio.sleep(5)

#     # Проверяем прокси
#     is_working = await check_proxy_aiohttp(ipv6_address[1], ipv6_address[3])
#     print(f"Is proxy working? {is_working}")

# asyncio.run(main())
