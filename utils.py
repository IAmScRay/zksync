"""
Сборник требуемых констант и вспомогательных методов
"""

import json

import requests

from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from web3 import Web3
from zksync2.manage_contracts.erc20_contract import ERC20Contract


DEPOSIT = 0
SWAP_USDC_USDT = 1
SWAP_USDT_USDC = 2
SWAP_ETH_USDC = 3
SWAP_USDC_ETH = 4

APPROVE_LIMIT = 5
SEND_MAIL = 8

ZERO_ADDRESS = Web3().to_checksum_address("0x0000000000000000000000000000000000000000")
PANCAKE_ZERO_ADDRESS = Web3().to_checksum_address("0x0000000000000000000000000000000000000002")


def get_token_balance(account: LocalAccount, web3: Web3, token_address: ChecksumAddress) -> int:
    """
    Получение баланса ERC-20 токена.
    :param account: объект blockchain-аккаунта.
    :param web3: ссылка на объект подключения к blockchain-узлу
    :param token_address: адрес контракта токена
    :return:
    """

    erc20Token = ERC20Contract(
        web3.eth,
        token_address,
        account
    )

    balance = erc20Token.balance_of(account.address)
    return balance


def get_gas_gwei() -> float:
    """
    Получение текущей цены за единицу газа в Ethereum Mainnet.
    :return: :class:`float`
    """
    return round(float(Web3.from_wei(
        json.loads(
            requests.get("https://beaconcha.in/api/v1/execution/gasnow").content
        )["data"]["fast"],
        "gwei"
    )), 4)


def from_usd_to_usdc(amount: float) -> int:
    """
    Конвертация USD в USDC с полной разрядностью.
    :param amount: сумма USD
    :return: :class:`int`
    """
    return int(amount * 10 ** 6)


def from_usdc_to_usd(amount: int) -> float:
    """
    Конвертация USDC в USD с полной разрядностью первого.
    :param amount: сумма USDC
    :return: :class:`float`
    """
    return round(amount / 10 ** 6, 6)
