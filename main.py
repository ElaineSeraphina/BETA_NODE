import requests  # Pastikan modul requests diimpor
import asyncio
import time
import uuid
from loguru import logger
from colorama import Fore, Style, init
import sys
import logging
logging.disable(logging.ERROR)

# Initialize colorama
init(autoreset=True)

# Customize loguru to use color for different log levels
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{message}</level>", colorize=True)
logger.level("INFO", color=f"{Fore.GREEN}")
logger.level("DEBUG", color=f"{Fore.CYAN}")
logger.level("WARNING", color=f"{Fore.YELLOW}")
logger.level("ERROR", color=f"{Fore.RED}")
logger.level("CRITICAL", color=f"{Style.BRIGHT}{Fore.RED}")

def show_copyright():
    print(Fore.MAGENTA + Style.BRIGHT + "Program Started" + Style.RESET_ALL)

PING_INTERVAL = 60
RETRIES = 120
TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxMzAzNDA0NTQyNjc4Nzk0MjQwIiwiaWF0IjoxNzMxMjQ1MTA5LCJleHAiOjE3MzI0NTQ3MDl9.RJemH8mMM1qeVRfvmoxWm93SukDlqeVN3uDFN3NRPmlZQ4FZ7uQ_kTzh3quLiXSrxBUAhVlWqdrA9E7XBU_X1w"  # Replace with your actual NP token

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}

def uuidv4():
    return str(uuid.uuid4())

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

proxy_auth_status = {}

async def render_profile_info(proxy):
    global browser_id, account_info

    try:
        np_session_info = load_session_info(proxy)
        
        if not proxy_auth_status.get(proxy):
            browser_id = uuidv4()
            response = await call_api("API_URL_HERE", {}, proxy)  # Replace with your API URL
            if response is None:
                return
            valid_resp(response)
            account_info = response["data"]
            
            if account_info.get("uid"):
                proxy_auth_status[proxy] = True
                save_session_info(proxy, account_info)
                logger.info(f"Authentication successful for proxy {proxy} account: {account_info}")
            else:
                handle_logout(proxy)
                return
        
        if proxy_auth_status[proxy]:
            await start_ping(proxy)

    except Exception as e:
        logger.error(f"Error in render_profile_info for proxy {proxy}: {e}")

async def call_api(url, data, proxy, max_retries=3):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://app.nodepay.ai",
    }

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=True)) as session:
        for attempt in range(max_retries):
            try:
                async with session.post(url, json=data, headers=headers, proxy=proxy, timeout=10) as response:
                    response.raise_for_status()
                    resp_json = await response.json()
                    return valid_resp(resp_json)
            except aiohttp.ClientResponseError as e:
                if e.status == 403:                    
                    return None
            except aiohttp.ClientConnectionError:
                pass
            except Exception:
                pass
            await asyncio.sleep(2 ** attempt)

    return None

async def start_ping(proxy):
    try:
        while True:
            await ping(proxy)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"{Fore.YELLOW}Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"{Fore.RED}Error in start_ping for proxy {proxy}: {e}")

async def ping(proxy):
    global last_ping_time, RETRIES, status_connect

    current_time = time.time()
    if proxy in last_ping_time and (current_time - last_ping_time[proxy]) < PING_INTERVAL:
        return

    last_ping_time[proxy] = current_time
    ping_urls = ["API_PING_URL_HERE"]  # Replace with your API ping URL

    for url in ping_urls:
        try:
            data = {
                "id": account_info.get("uid"),
                "browser_id": browser_id,
                "timestamp": int(time.time()),
                "version": '2.2.7'
            }
            logger.warning(f"Starting ping task for proxy {proxy} Data: {data}")
            response = await call_api(url, data, proxy)
            if response["code"] == 0:
                logger.info(f"{Fore.CYAN}Ping successful via proxy {proxy} - {response}")
                RETRIES = 0
                status_connect = CONNECTION_STATES["CONNECTED"]
                return 
            else:
                logger.error(f"{Fore.RED}Ping failed via proxy {proxy} - {response}")
                handle_ping_fail(proxy, response)
        except Exception as e:
            logger.error(f"{Fore.RED}Ping error via proxy {proxy}: {e}")

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
    global status_connect, account_info

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    save_status(proxy, None)
    logger.info(f"{Fore.YELLOW}Logged out and cleared session info for proxy {proxy}")

def load_proxies_from_file(file_name):
    try:
        with open(file_name, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies from file: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

def save_status(proxy, status):
    pass

def save_session_info(proxy, data):
    data_to_save = {
        "uid": data.get("uid"),
        "browser_id": browser_id
    }
    pass

def load_session_info(proxy):
    return {}

async def main():
    show_copyright()
    print("Welcome to the main program!")
        
    # Token is now hardcoded in the script, no need to load from a file

    # Load proxies from the local file proxy.txt
    proxies = load_proxies_from_file("proxy.txt")  # File is expected to be in the same directory

    while True:
        tasks = {asyncio.create_task(render_profile_info(proxy)): proxy for proxy in proxies}

        done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            tasks.pop(task)

        for proxy in set(proxies) - set(tasks.values()):
            new_task = asyncio.create_task(render_profile_info(proxy))
            tasks[new_task] = proxy

        await asyncio.sleep(3)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
