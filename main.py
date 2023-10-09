import json
import time
from os.path import exists
from pathlib import Path
from random import shuffle

from web3 import Web3

import utils
from config import Configuration

from modules.cross_chain_nft import CrossChainNFT
from modules.dmail import Dmail
from modules.flow import Flow
from modules.mute import Mute
from modules.pancakeswap import PancakeSwap
from modules.space_fi import SpaceFi
from modules.syncswap import SyncSwap
from modules.tevaera import TevaEra
from modules.velocore import Velocore
from modules.woofi import WooFi

modules = [
    Dmail,
    Mute,
    PancakeSwap,
    Velocore,
    SpaceFi,
    CrossChainNFT,
    SyncSwap,
    TevaEra,
    WooFi
]


filename = ""
while filename == "":
    name = input("Введите имя файла, из которого будут прочитаны настройки: ")

    if not exists(Path.cwd().joinpath(f"resources/{name}.json")):
        print(f"Файл {name}.json не существует! Проверьте правильность имени и повторите попытку.")
    else:
        filename = name

config = Configuration(filename)

filename = ""
while filename == "":
    name = input("Введите имя файла, из которого будут прочитаны адреса и приватные ключи (без расширения .json): ")

    if not exists(Path.cwd().joinpath(f"resources/{name}.json")):
        print(f"Файл {name}.json не существует! Проверьте правильность имени и повторите попытку.")
    else:
        filename = name

file = open(f"resources/{filename}.json", "r")
accounts = json.loads(file.read())["accounts"]
file.close()

print(f"Загружено аккаунтов: {len(accounts)}\n")

start = int(input("Укажите индекс адреса, с которого начнутся операции: "))
end = int(input("Укажите индекс адреса, на котором закончатся операции: "))
accounts = accounts[start:end]
print(f"Кол-во адресов для проведения операции: {len(accounts)}")
print(f"Первый адрес: {accounts[0]['address']} \n"
      f"• приватный ключ - {accounts[0]['pk']}\n"
      f"• прокси-сервер – {accounts[0]['proxy'] if 'proxy' in accounts[0] else 'отсутствует'}\n")
print(f"Последний адрес: {accounts[len(accounts) - 1]['address']} \n"
      f"• приватный ключ - {accounts[len(accounts) - 1]['pk']}\n"
      f"• прокси-сервер – {accounts[len(accounts) - 1]['proxy'] if 'proxy' in accounts[len(accounts) - 1] else 'отсутствует'}\n")

time.sleep(5)

shuffle(accounts)

accounts_list = []
proxies = {}
for account in accounts:
    a = Web3().eth.account.from_key(account["pk"])
    accounts_list.append(a)

    if "proxy" in account:
        proxies[a.address] = account["proxy"]

flow_len = int(
    input(
        f"Реализовано модулей: {len(modules)}.\n"
        f"Выберите длину flow для работы: "
    )
)

if flow_len > len(modules):
    raise ValueError("Запрашиваемая длина больше возможной!")

# TODO: убрать это после отработки!
if flow_len == -1:
    for account in accounts_list:
        pancake = PancakeSwap(
            w3_url="https://withered-powerful-sky.zksync-mainnet.discover.quiknode.pro/a63cf3dfa610c1c523d8143fd5fa0f7318c2c35e/",
            proxy=proxies[account.address] if account.address in proxies else "",
            account=account,
            config=config,
            o_id=utils.SWAP_USDT_USDC
        )

        pancake.run()

    exit(0)

time_start = int(time.time())

for account in accounts_list:
    flow = Flow.get_random_flow(
        length=flow_len,
        account=account,
        w3_url="https://withered-powerful-sky.zksync-mainnet.discover.quiknode.pro/a63cf3dfa610c1c523d8143fd5fa0f7318c2c35e/",
        proxy=proxies[account.address] if account.address in proxies else "",
        config=config
    )

    flow.run()

time_end = int(time.time())

diff = time_end - time_start
minutes = diff // 60
seconds = diff % 60
print(f"Скрипт завершил работу! (прошло {minutes} мин., {seconds} сек.)")
