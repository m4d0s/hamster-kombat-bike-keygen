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
    events = config['EVENTS']
    keys = list(events.keys())
    semaphore = asyncio.Semaphore(config['GEN_PROXY'])
    logger = get_logger()
    pool = await get_pool()

    async with aiohttp.ClientSession() as session:
        i = 0
        while True:
            tasks = []
            for _ in range(config['GEN_PROXY']):
                async with semaphore:
                    task = asyncio.create_task(new_key(session, keys[i % len(events)], pool=pool, logger=logger, id=i))
                    tasks.append(task)
                    i += 1

            # Use asyncio.gather and handle exceptions gracefully
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                logger.error(f"Error during task execution: {e}")



if __name__ == '__main__':
    asyncio.run(main())
