import json
import random
from typing import Any

import web3
from eth_typing import ChecksumAddress


class Configuration:
    """
    Класс, который хранит в себе удобные методы для получения параметров,
    адресов и прочих данных для взаимодействия с модулями скрипта.
    """

    def __init__(self, filename):
        self.filename = filename
        self.data = {}

        self.update()

    def update(self) -> None:
        file = open(f"resources/{self.filename}.json", "r")
        self.data = json.loads(file.read())
        file.close()

    def get_token_address(self, token: str) -> ChecksumAddress:
        """
        Получение хэш-адреса контракта токена.
        :param token: идентификатор токена (USDC, USDT, ...)
        :return: :class:`ChecksumAddress`
        """

        data = self.data["erc20Tokens"]
        return web3.Web3.to_checksum_address(data[token])

    def get_project_id(self, project: str) -> int:
        """
        Получение ID проекта.
        :param project: название проекта (Mute, Velocore, ...)
        :return: :class:`int`
        """

        data = self.data["projects"][project]
        return data["id"]

    def get_contract_address(self, project: str, contract_type: str = "router") -> ChecksumAddress:
        """
        Получение хэш-адреса требуемого контракта для модуля.

        :param project: название проекта (Mute, Velocore, ...)
        :param contract_type: тип адреса (описан в ``config.json`` в параметрах каждого модуля)
        :return: :class:`ChecksumAddress`
        """

        addr_list = self.data["projects"][project]["addresses"]

        if contract_type not in addr_list:
            raise ValueError(f"{contract_type}: тип адреса отсутствует в списке доступных ({list(addr_list.keys())})")

        return web3.Web3.to_checksum_address(addr_list[contract_type])

    def get_contract_abi(self, project: str, abi_type: str = "router") -> str:
        """
        Получение `ABI <https://docs.soliditylang.org/en/develop/abi-spec.html>`_ для требуемого контракта.

        :param project: название проекта (Mute, Velocore, ...)
        :param abi_type: тип адреса (описан в ``config.json`` в параметрах каждого модуля)
        :return: :class:`list`
        """
        data = self.data["projects"][project]
        abi_list = data["abi"]

        if abi_type not in abi_list:
            raise ValueError(f"{abi_type}: ABI отсутствует в списке доступных ({list(abi_list.keys())})")

        abi_filename = abi_list[abi_type]

        abi_file = open(f"resources/{abi_filename}", "r")
        abi = json.loads(abi_file.read())["abi"]

        abi_file.close()
        return abi

    def get_additional(self, project: str, key: str) -> Any:
        """
        Получение доп. параметров, которые требуются для работы модуля.

        Примером служит модуль :class:`Dmail`: ему нужен список эл. почт,
        которые будут задействованы в отправке письма.
        :param project: название проекта (Dmail, ...)
        :param key: ключ, по которому будут получены параметры
        :return: :class:`Any`, так как на выходе может быть как список,
        так и словарь, так и любое другое значение (текст, число, ...).
        """
        data = self.data["projects"][project]

        if "additional" not in data:
            raise ValueError(f"поле \"additional\" отсутствует в настройках проекта {project}")

        add_data = data["additional"]
        if key not in add_data:
            raise ValueError(f"поле \"{key}\" отсутствует в доп. данных проекта {project}")

        return add_data[key]

    def get_random_tx_sleep(self) -> int:
        """
        Получение случайного времени для "сна" между формированием и
        отправкой транзакции в сеть.

        :return: :class:`int`
        """
        values = self.data["randomTxSleepTime"]

        return random.randint(values["min"], values["max"])

    def get_random_approve_sleep(self) -> int:
        """
        Получение случайного времени для "сна" между формированием и
        отправкой транзакции увеличения лимита расходов в сеть.

        :return: :class:`int`
        """
        values = self.data["randomApproveSleepTime"]

        return random.randint(values["min"], values["max"])

    def get_slippage(self, project: str) -> float:
        """
        Получение случайного значения "проскальзывания" во время
        просчёта минимальной получаемой суммы при swap-операции.

        :param project: название проекта (Mute, Velocore, ...)
        :return: :class:`float`
        """
        return self.data["slippage"][project]

    def get_max_gwei(self) -> int:
        """
        Получение максимально допустимого значения цены за
        единицу газа, при которой будут отправлены транзакции.

        Значение указано для Ethereum Mainnet, так как комиссии
        зависят от загруженности L1.
        :return: :class:`int`
        """
        return self.data["maxGwei"]
