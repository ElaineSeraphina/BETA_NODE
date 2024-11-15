import asyncio
import aiohttp
import json
import time
import uuid
from loguru import logger

# Constants
NP_TOKEN = "WRITE_YOUR_NP_TOKEN_HERE"
PING_INTERVAL = 30  # seconds
RETRIES = 60  # Global retry counter for ping failures

DOMAIN_API = {
    "SESSION": "https://api.nodepay.ai/api/auth/session",
    "PING": "https://nw2.nodepay.ai/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
token_info = NP_TOKEN
browser_id = None
account_info = {}

# Semaphore to limit the number of concurrent tasks
semaphore = asyncio.Semaphore(200)  # Maximize concurrency

async def uuidv4():
    return str(uuid.uuid4())

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

async def render_profile_info(proxy, session):
    global browser_id, token_info, account_info

    try:
        np_session_info = load_session_info(proxy)

        if not np_session_info:
            response = await call_api(DOMAIN_API["SESSION"], {}, proxy, session)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(proxy, account_info)
                await start_ping(proxy, session)
            else:
                handle_logout(proxy)
        else:
            account_info = np_session_info
            await start_ping(proxy, session)
    except Exception as e:
        logger.error(f"Error in render_profile_info for proxy {proxy}: {e}")
        error_message = str(e)
        if any(phrase in error_message for phrase in [
            "sent 1011 (internal error) keepalive ping timeout; no close frame received",
            "500 Internal Server Error"
        ]):
            logger.info(f"Removing error proxy from the list: {proxy}")
            remove_proxy_from_list(proxy)
            return None
        else:
            logger.error(f"Connection error: {e}")
            return proxy

async def call_api(url, data, proxy, session):
    try:
        async with session.post(url, json=data, proxy=f"http://{proxy}", timeout=10) as response:
            response.raise_for_status()
            return valid_resp(await response.json())
    except aiohttp.ClientError as e:
        logger.error(f"Error during API call: {e}")
        raise ValueError(f"Failed API call to {url}")

async def start_ping(proxy, session):
    try:
        await ping(proxy, session)
        while True:
            await asyncio.sleep(PING_INTERVAL)
            await ping(proxy, session)
    except asyncio.CancelledError:
        logger.info(f"Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping for proxy {proxy}: {e}")

async def ping(proxy, session):
    global RETRIES, status_connect

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time())
        }

        response = await call_api(DOMAIN_API["PING"], data, proxy, session)
        if response["code"] == 0:
            logger.info(f"Ping successful via proxy {proxy}: {response}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(proxy, response)
    except Exception as e:
        logger.error(f"Ping failed via proxy {proxy}: {e}")
        handle_ping_fail(proxy, None)

def handle_ping_fail(proxy, response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout(proxy)
    elif RETRIES < 2:
        status_connect = CONNECTION_STATES["DISCONNECTED"]
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout(proxy):
    global token_info, status_connect, account_info

    token_info = None
    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    save_status(proxy, None)
    logger.info(f"Logged out and cleared session info for proxy {proxy}")

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

def save_status(proxy, status):
    pass

def save_session_info(proxy, data):
    pass

def load_session_info(proxy):
    return {}

def is_valid_proxy(proxy):
    return True

def remove_proxy_from_list(proxy):
    pass

async def render_profile_info_with_semaphore(proxy, session):
    async with semaphore:
        return await render_profile_info(proxy, session)

async def main():
    async with aiohttp.ClientSession() as session:  # Create one shared session for all requests
        with open('proxy.txt', 'r') as f:
            all_proxies = f.read().splitlines()

        active_proxies = [proxy for proxy in all_proxies[:100] if is_valid_proxy(proxy)]  # Default 100 proxies
        tasks = [asyncio.create_task(render_profile_info_with_semaphore(proxy, session)) for proxy in active_proxies]

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
