import asyncio
import aiohttp
import aiofiles
import json

from database import get_pool, insert_key_generation
from generate import get_logger, delay, get_key

# Load configuration
MINING_POOL = None
config = json.loads(open('config.json').read())
SCHEMAS = config['SCHEMAS']
farmed_keys, attempts = 0, {}
users = [x for x in config['EVENTS']]

async def load_config(file_path):
    async with aiofiles.open(file_path, mode='r') as f:
        return json.loads(await f.read())

async def new_key(session, game, pool):
    try:
        key = await get_key(session, game)
        if key:
            logger.info(f"Key for game {game} generated: {key}")
            await insert_key_generation(user_id=config['DEV_ID'], key=key, key_type=game, pool=pool)
        else:
            logger.warning(f"Failed to generate key for game {game}")
    except Exception as e:
        logger.error(f"Error generating key for {game}: {e}")

logger = get_logger()

async def main():
    global MINING_POOL, logger
    config = await load_config('config.json')
    events = [x for x in config['EVENTS'] if not config['EVENTS'][x]['DISABLED']]
    limit = config['GEN_PROXY']
    semaphore = asyncio.Semaphore(limit)
    await get_pool()

    async with aiohttp.ClientSession() as session:
        tasks, i = [], -1
        while True:
            i+=1; i%=len(events) * (60 // len(events) + 1)
            tasks = [t for t in tasks if not t.done()]
            if i == 0:
                logger.info(f"Generating keys in process: {len(tasks)}")
            async with semaphore:
                if len(tasks) < limit:
                    tasks.append(asyncio.create_task(new_key(session, events[i%len(events)], MINING_POOL)))
                await delay(1000, "Generating delay")

if __name__ == '__main__':
    asyncio.run(main())
