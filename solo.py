import logging
import asyncio
import aiohttp
import aiofiles
import asyncpg
import json
import os

from generate import get_key, logger
from database import insert_key_generation, log_timestamp
from telegram import POOL

# Function to load the JSON config asynchronously
async def load_config(file_path:str):
    async with aiofiles.open(file_path, mode='r') as f:
        return json.loads(await f.read())

async def new_key(session:aiohttp.ClientSession, game:str, api_token:str, pool:asyncpg.Pool) -> None:
    logger.info(f"Generating new key for {game}")
    try:
        key = await get_key(session, game)
        if key:
            logger.info(f"Key for game {game} generated: {key}")
        else:
            logger.warning(f"Failed to generate key for game {game}")
        await insert_key_generation(int(api_token.split(":")[0]), key, game, used=False, pool=pool)
    except Exception as e:
        logger.error(f"Error generating key for {game}: {e}")

async def main() -> None:
    config = await load_config('config.json')
    api_token = config['API_TOKEN']
    events = [x for x in config['EVENTS']]
    limit = load_config('config.json')['COUNT']
    semaphore = asyncio.Semaphore(limit)

    logger.basicConfig(level=logging.INFO,
                        filename=os.path.join('logs', log_timestamp() + '.log'),
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async with aiohttp.ClientSession() as session:
        i = 0
        while True:
            tasks = []
            while len(tasks) < limit:
                async with semaphore:
                    tasks.append(new_key(session, events[i % len(events)], api_token, pool=POOL))
                    i += 1
            await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
