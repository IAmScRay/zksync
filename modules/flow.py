import random

from eth_account.signers.local import LocalAccount

from config import Configuration

from modules.dmail import Dmail
from modules.mute import Mute
from modules.pancakeswap import PancakeSwap
from modules.space_fi import SpaceFi
from modules.syncswap import SyncSwap
from modules.tevaera import TevaEra
from modules.velocore import Velocore
from modules.cross_chain_nft import CrossChainNFT
from modules.woofi import WooFi


class Flow:
    """
    Класс, который хранит в себе последовательность (flow) работы модулей.
    """

    @staticmethod
    def get_random_flow(
            length: int,
            account: LocalAccount,
            w3_url: str,
            proxy: str,
            config: Configuration
    ):
        """
        Выбор случайной последовательности модулей заданной длины.
        :param length: длина последовательности
        :param account: объект blockchain-аккаунта
        :param w3_url: ссылка на blockchain-узел
        :param proxy: ссылка на proxy-сервер, через который будет произведено подключение к узлу
        :param config: объект конфигурации
        """
        modules = [
            CrossChainNFT,
            Dmail,
            Mute,
            PancakeSwap,
            SpaceFi,
            SyncSwap,
            TevaEra,
            Velocore,
            WooFi
        ]

        random.shuffle(modules)

        return Flow(
            account=account,
            modules=modules[0:length],
            w3_url=w3_url,
            proxy=proxy,
            config=config
        )

    def __init__(
            self,
            account: LocalAccount,
            modules: list,
            w3_url: str,
            proxy: str,
            config: Configuration
    ):
        """
        Инициализация объекта.
        :param account: объект blockchain-аккаунта
        :param modules: список модулей, которые будут задействованы
        :param w3_url: ссылка на узел blockchain-сети
        :param proxy: ссылка на proxy-сервер, через который будет произведено подключение к узлу
        :param config: объект конфигурации
        """
        self.account = account
        self.modules = modules
        self.w3_url = w3_url
        self.proxy = proxy
        self.config = config

    def run(self):
        """
        Запуск работы.
        """
        for module in self.modules:
            m = module(
                w3_url=self.w3_url,
                proxy=self.proxy,
                account=self.account,
                config=self.config
            )
            m.run()
