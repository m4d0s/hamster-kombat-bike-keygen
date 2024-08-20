import logging
import asyncio
import aiohttp
import asyncpg
import json

from generate import get_key, get_logger
from database import insert_key_generation, get_pool, get_proxies

with open('config.json') as f:
    config = json.load(f)

async def new_key(session: aiohttp.ClientSession, game: str, pool: asyncpg.Pool, logger: logging.Logger) -> None:
    logger.info(f"Generating new key for {game}")
    try:
        key = await get_key(session, game)
        if config['DEBUG_KEY'] in key:
            game = config['DEBUG_GAME']
        if key:
            logger.info(f"Key for game {game} generated: {key}")
            await insert_key_generation(0, key, game, used=False, pool=pool)  # Ensure pool is passed
        else:
            logger.warning(f"Failed to generate key for game {game}")
    except Exception as e:
        logger.error(f"Error generating key for {game}: {e}")

async def generating_loop(pool: asyncpg.Pool, limit: int, logger: logging.Logger) -> None:
    semaphore = asyncio.Semaphore(limit)
    events = [x for x in config['EVENTS']]
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(limit):
            async with semaphore:
                task = asyncio.create_task(new_key(session, events[i % len(events)], pool=pool, logger=logger))
                tasks.append(task)
        await asyncio.gather(*tasks)

async def main() -> None:
    logger = get_logger()
    pool = await get_pool()
    proxy = await get_proxies(pool)
    limit = min(config['GEN_PROXY'], int(len(proxy) * 0.8) + 1)

    while True:
        await generating_loop(pool, limit, logger)

if __name__ == '__main__':
    asyncio.run(main())
