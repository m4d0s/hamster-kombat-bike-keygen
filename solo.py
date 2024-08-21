import logging
import asyncio
import aiohttp
import aiofiles
import asyncpg
import json
import os
import sys

from generate import get_key, get_logger
from database import insert_key_generation, get_pool, get_proxies


# Function to load the JSON config asynchronously

with open('config.json') as f:
    config = json.load(f)

async def new_key(session: aiohttp.ClientSession, game: str, pool: asyncpg.Pool, logger: logging.Logger) -> None:
    logger.info(f"Generating new key for {game}")
    try:
        key = await get_key(session, game, pool)
        if key:
            logger.info(f"Key for game {game} generated: {key}")
            await insert_key_generation(0, key, game, used=False, pool=pool)
        else:
            logger.warning(f"Failed to generate key for game {game}")

    except Exception as e:
        logger.error(f"Error generating key for {game}: {e}")

async def main() -> None:
    pool = await get_pool(True)
    events = [x for x in config['EVENTS']]
    proxy = await get_proxies(pool)
    limit = min(int(len(proxy)*0.8+1), config['GEN_PROXY'])
    logger = get_logger()
    

    async with aiohttp.ClientSession() as session:
        i = 0
        while True:
            tasks = []
            while len(tasks) < limit:
                tasks.append(asyncio.create_task(new_key(session, events[i % len(events)], pool=pool, logger=logger)))
                i += 1
            await asyncio.gather(*tasks)

if __name__ == '__main__' and config['MINING']:
    asyncio.run(main())
