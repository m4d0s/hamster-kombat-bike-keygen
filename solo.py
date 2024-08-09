import logging
import asyncio
import aiohttp
import aiofiles
import json
import os

from generate import get_key
from database import insert_key_generation, log_timestamp
from telegram import POOL

# Function to load the JSON config asynchronously
async def load_config(file_path):
    async with aiofiles.open(file_path, mode='r') as f:
        return json.loads(await f.read())

async def new_key(session, game, api_token, pool):
    logging.info(f"Generating new key for {game}")
    try:
        key = await get_key(session, game)
        if key:
            logging.info(f"Key for game {game} generated: {key}")
        else:
            logging.warning(f"Failed to generate key for game {game}")
        await insert_key_generation(int(api_token.split(":")[0]), key, game, used=False, pool=pool)
    except Exception as e:
        logging.error(f"Error generating key for {game}: {e}")

async def main():
    config = await load_config('config.json')
    api_token = config['API_TOKEN']
    events = [x for x in config['EVENTS']]
    limit = load_config('config.json')['COUNT']
    semaphore = asyncio.Semaphore(limit)

    logging.basicConfig(level=logging.INFO,
                        filename=os.path.join('logs', log_timestamp() + '.log'),
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async with aiohttp.ClientSession() as session:
        i = 0
        while True:
            tasks = []
            while len(tasks) < limit:
                async with semaphore:
                    tasks.append(new_key(session, events[i % len(events)], api_token, POOL))
                    i += 1
            await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
