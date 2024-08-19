import logging
import asyncio
import aiohttp
import aiofiles
import asyncpg
import json
import os

from generate import get_key, get_logger
from database import insert_key_generation, get_pool

async def new_key(session:aiohttp.ClientSession, game:str, pool:asyncpg.Pool, logger:logging.Logger, id:int = 0) -> None:
    config = json.loads(open('config.json').read())
    logger.info(f"Generating new key for {game}")
    try:
        key = await get_key(session, game)
        if config['DEBUG_KEY'] in key:
            game = config['DEBUG_GAME']
        if key:
            logger.info(f"Key for game {game} generated: {key}")
            await insert_key_generation(id, key, game, used=False, pool=pool)
        else:
            logger.warning(f"Failed to generate key for game {game}")
        
    except Exception as e:
        logger.error(f"Error generating key for {game}: {e}")

async def main() -> None:
    config = json.loads(open('config.json').read())
    events = [x for x in config['EVENTS']]
    semaphore = asyncio.Semaphore(config['GEN_PROXY'])
    logger = get_logger()
    pool = await get_pool()
    # await insert_user(config['BOT_ID'], config['BOT_USERNAME'], pool=pool)

    async with aiohttp.ClientSession() as session:
        i = 0
        while True:
            tasks = []
            while len(tasks) < config['GEN_PROXY']:
                async with semaphore:
                    tasks.append(new_key(session, events[i % len(events)], pool=pool, logger=logger))
                    i += 1
            await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
