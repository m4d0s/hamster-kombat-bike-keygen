from database import (get_user, get_cached_data as get_cached, write_cached_data)

#Cache funcs
async def set_cached_data(user:int, data:dict, pool=None):
    data_copy = data.copy()
    data_copy.pop('id', None)
    data_copy.pop('lang', None)
    data_copy.pop('user_id', None)
    data_copy.pop('right', None)
    data_copy.pop('try', None)
    
    await write_cached_data(user, data_copy, pool=pool) 

async def get_cached_data(user_id:int) -> tuple:
    user = await get_user(user_id, pool=None)
    cache_default = {'user_id':None, 
                     'welcome':None, 
                     'loading':None, 
                     'report':None, 
                     'error':None, 
                     'tasks': None, 
                     'addtask': None, 
                     'deletetask': None}
    if not user:
        cache_default['user_id'] = user_id
        await set_cached_data(user_id, cache_default)
    config = await get_cached(user_id, pool=None)
    config = config if config is not None else cache_default
    
    config['process'] = config['process'] if 'process' in config else True
    config['lang'] = user['lang'] if user and user['lang'] else 'en'
    config['right'] = user['right'] if user and user['right'] else 0
    config['try'] = user['try'] if user and user['try'] else 16
    
    return config
