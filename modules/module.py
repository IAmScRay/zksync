import time
from abc import ABC, abstractmethod

from eth_account.account import LocalAccount
from eth_typing import ChecksumAddress
from web3 import Web3, HTTPProvider
from zksync2.manage_contracts.erc20_contract import ERC20Contract

import utils
from config import Configuration


class Module(ABC):
    """
    Абстрактный класс для подключения модулей.

    Присутствует поддержка установки **proxy**-сервера для подключения к узлу blockchain-сети.
    """

    def __init__(
            self,
            w3_url: str,
            proxy: str,
            account: LocalAccount,
            config: Configuration
    ):
        """
        Инициализация объекта модуля.
        :param w3_url: ссылка на узел blockchain-сети
        :param proxy: ссылка на proxy-сервер, через который будет произведено подключение к узлу
        :param account: объект blockchain-аккаунта
        :param config: объект конфигурации
        """

        if proxy != "":
            proxy_args = {
                "proxies": {
                    "http": proxy,
                    "https": proxy
                }
            }
        else:
            proxy_args = {}

        self.w3_provider = Web3(HTTPProvider(w3_url, request_kwargs=proxy_args))
        self.account = account
        self.config = config

    def __call__(self, *args, **kwargs):
        """
        Вспомогательная функция, которая позволяет инициализировать объект как функцию.
        :param args: системные аргументы в виде списка
        :param kwargs: системные аргументы в виде словаря
        :return: :class:`Module`
        """
        return Module(*args, **kwargs)

    def get_provider(self) -> Web3:
        """
        Получение ссылки на объект подключения к blockchain-узлу.
        :return: :class:`Web3`
        """
        return self.w3_provider

    def get_account(self) -> LocalAccount:
        """
        Получение ссылки на аккаунт в blockchain-сети.
        :return: :class:`LocalAccount`
        """
        return self.account

    def get_config(self) -> Configuration:
        """
        Получение ссылки на объект конфигурации.
        :return: :class:`Configuration`
        """
        return self.config

    def has_enough_allowance(
            self,
            contract: ChecksumAddress,
            token: str,
            amount: int
    ) -> bool:
        """
        Проверяет, достаточно ли имеющегося лимита расходов для контракта данного модуля,
        которому нужно взаимодействовать с указанным токеном.

        :param contract: адрес контракта модуля
        :param token: идентификатор токена (USDC, USDT, ...)
        :param amount: количество токенов в полной разрядности (1 USDC = 1 000 000 у.е., потому что USDC имеет 6 нолей)
        :return: ``True``, если лимита достаточно, ``False`` – когда требуется увеличить лимит
        """
        token_address = self.config.get_token_address(token)

        erc20_contract = ERC20Contract(
            self.w3_provider.eth,
            token_address,
            self.account
        )

        allowance = erc20_contract.allowance(
            self.account.address,
            contract
        )

        return allowance >= amount

    def approve(
            self,
            contract: ChecksumAddress,
            token: str,
            amount: int
    ) -> bool:
        """
        Подтверждение нового лимита расходов для контракта, которому нужно
        взаимодействовать с указанным токеном
        :param contract: адрес контракта модуля
        :param token: идентификатор токена (USDC, USDT, ...)
        :param amount: количество токенов в полной разрядности (1 USDC = 1 000 000 у.е., потому что USDC имеет 6 нолей)
        :return: ``True`` если лимит был успешно увеличен,
        ``False`` – лимит не был увеличен из-за ошибки или высокой цены за газ
        """
        token_address = self.config.get_token_address(token)

        erc20_contract = ERC20Contract(
            self.w3_provider.eth,
            token_address,
            self.account
        )

        gas_price = utils.get_gas_gwei()
        if gas_price > self.config.get_max_gwei():
            print(f"Адрес {self.account}: слишком высокая цена за газ!\n"
                  f"• требуется {self.config.get_max_gwei()} GWei или меньше\n"
                  f"• текущая цена за газ – {gas_price} GWei\n")

            return False

        tx_data = {
            "from": self.account.address,
            "gasPrice": self.w3_provider.eth.gas_price,
            "nonce": self.w3_provider.eth.get_transaction_count(self.account.address)
        }

        approve_gas = erc20_contract.contract.functions.approve(
            contract,
            amount
        ).estimate_gas(tx_data)

        tx_data["gas"] = approve_gas

        sleep_time = self.config.get_random_approve_sleep()
        print(f"Адрес {self.account.address}: подтверждение лимита расходов для контракта {contract}\n"
              f"\"Спим\" {sleep_time} сек...\n")

        time.sleep(sleep_time)

        try:
            receipt = erc20_contract.approve(
                contract,
                amount,
                approve_gas
            )
        except ValueError:
            print(f"Адрес {self.get_account().address}: недостаточно баланса ETH для транзакции!")
            return False

        status = receipt.get("status")
        if status == 1:
            print(f"Адрес {self.get_account().address}: лимит расходов успешно увеличен!\n"
                  f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
            return True
        else:
            print(f"Адрес {self.account.address}: \t произошла ошибка при выполнении транзакции!\n"
                  f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
            return False

    @abstractmethod
    def run(self):
        """
        Запуск модуля. Каждый модуль описывает свою логику и работу тут.

        В своём классе модуль может добавлять любые другие методы для работы,
        но ``run()`` – это **основная** точка входа.
        """
        pass

    @abstractmethod
    def get_id(self) -> int:
        """
        Получение ID проекта.
        :return: :class:`int`
        """
        pass
