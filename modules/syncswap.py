import random
import sys
import time

from eth_abi import abi
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from web3.exceptions import ContractLogicError

import utils
from config import Configuration
from modules.module import Module


class SyncSwap(Module):

    def __init__(
            self,
            w3_url: str,
            proxy: str,
            account: LocalAccount,
            config: Configuration
    ):
        super().__init__(w3_url, proxy, account, config)

        self.contract = self.get_provider().eth.contract(
            address=config.get_contract_address("SyncSwap"),
            abi=config.get_contract_abi("SyncSwap")
        )

        self.o_id = 0

    def get_id(self) -> int:
        return self.get_config().get_project_id("SyncSwap")

    def run(self):
        rand_op = random.randint(1, 4)
        if rand_op == 1:
            print(f"[SyncSwap] Адрес {self.get_account().address}: будет проведена swap-операция USDC -> USDT")
            self.o_id = utils.SWAP_USDC_USDT
        elif rand_op == 2:
            print(f"[SyncSwap] Адрес {self.get_account().address}: будет проведена swap-операция ETH -> USDC")
            self.o_id = utils.SWAP_ETH_USDC
        elif rand_op == 3:
            print(f"[SyncSwap] Адрес {self.get_account().address}: будет проведена swap-операция USDT -> USDC")
            self.o_id = utils.SWAP_USDT_USDC
        elif rand_op == 4:
            print(f"[SyncSwap] Адрес {self.get_account().address}: будет проведена swap-операция USDC -> ETH")
            self.o_id = utils.SWAP_USDC_ETH

        if (
                self.o_id == utils.SWAP_USDC_USDT and
                utils.get_token_balance(
                    self.get_account(),
                    self.get_provider(),
                    self.get_config().get_token_address("USDC")
                ) < utils.from_usd_to_usdc(1.0)
        ) or (
                self.o_id == utils.SWAP_USDT_USDC and
                utils.get_token_balance(
                    self.get_account(),
                    self.get_provider(),
                    self.get_config().get_token_address("USDT")
                ) < utils.from_usd_to_usdc(1.0)
        ) or (
                self.o_id == utils.SWAP_USDC_ETH and
                utils.get_token_balance(
                    self.get_account(),
                    self.get_provider(),
                    self.get_config().get_token_address("USDC")
                ) < utils.from_usd_to_usdc(1.0)
        ):
            print(f"Адрес {self.get_account().address}: недостаточно баланса для операций над ERC-20 токенами!\n"
                  f"Будет проведена swap-операция ETH -> USDC")
            self.o_id = utils.SWAP_ETH_USDC

        if self.o_id == utils.SWAP_ETH_USDC:
            eth_balance = self.get_provider().eth.get_balance(self.get_account().address, "latest")
            print(f"Баланс: {self.get_provider().from_wei(eth_balance, 'ether')} ETH")

            rand_portion = random.randint(10, 20)
            portion = eth_balance // 100 * rand_portion
            print(f"Будет проведено {rand_portion}% от баланса ({self.get_provider().from_wei(portion, 'ether')} ETH)")

            pool_addr = self.get_pool("WETH", "USDC")
            if pool_addr != utils.ZERO_ADDRESS:

                current_gas_price = utils.get_gas_gwei()
                if current_gas_price > self.get_config().get_max_gwei():
                    print(f"[SyncSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                          f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                          f"• текущая цена – {current_gas_price} GWei\n")
                    return

                tx_data = {
                    "from": self.get_account().address,
                    "value": portion,
                    "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address),
                    "gasPrice": self.get_provider().eth.gas_price
                }

                min_out = self.get_min_out(
                    pool_addr,
                    "WETH",
                    portion
                )

                steps = [{
                    "pool": pool_addr,
                    "data": abi.encode(
                        [
                            "address",
                            "address",
                            "uint8"
                        ],
                        [
                            self.get_config().get_token_address("WETH"),
                            self.get_account().address,
                            1
                        ]
                    ),
                    "callback": utils.ZERO_ADDRESS,
                    "callbackData": "0x"
                }]

                paths = [{
                    "steps": steps,
                    "tokenIn": utils.ZERO_ADDRESS,
                    "amountIn": portion
                }]

                deadline = int(time.time()) + 1800

                gas = 0
                while gas == 0:
                    try:
                        gas = self.contract.functions.swap(
                            paths,
                            min_out,
                            deadline
                        ).estimate_gas(tx_data)
                    except ContractLogicError:
                        print(f"[SyncSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                              f"Будет произведена попытка просчёта снова.\n")

                        min_out = self.get_min_out(
                            pool_addr,
                            "WETH",
                            portion
                        )

                tx_data["gas"] = gas

                swap_tx = self.contract.functions.swap(
                    paths,
                    min_out,
                    deadline
                ).build_transaction(tx_data)

                print(f"Адрес {self.get_account().address}: swap-операция ETH -> USDC\n"
                      f"• на входе {self.get_provider().from_wei(portion, 'ether')} ETH\n"
                      f"• на выходе {utils.from_usdc_to_usd(min_out)} USDC")

                rand_sleep = self.get_config().get_random_tx_sleep()
                print(f"\"Спим\" {rand_sleep} секунд...")
                time.sleep(rand_sleep)

                signed = self.get_account().sign_transaction(swap_tx)
                try:
                    sent_tx = self.get_provider().eth.send_raw_transaction(signed.rawTransaction)
                except ValueError:
                    print(f"Адрес {self.get_account().address}: недостаточно баланса ETH для транзакции!\n")
                    return

                receipt = self.get_provider().eth.wait_for_transaction_receipt(sent_tx)

                status = receipt.get("status")
                if status == 1:
                    print(f"Адрес {self.get_account().address}: транзакция успешна!\n"
                          f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
                else:
                    print(f"Адрес {self.get_account().address}: произошла ошибка при выполнении транзакции!\n"
                          f"• хэш транзакции: {receipt['transactionHash'].hex()}\n",
                          file=sys.stderr
                          )
            else:
                print(f"Адрес {self.get_account().address}: произошла ошибка при получении данных из пула!\n"
                      f"(был получен нулевой адрес пула – {utils.ZERO_ADDRESS})\n")
        elif self.o_id == utils.SWAP_USDC_ETH:
            usdc_balance = utils.get_token_balance(
                self.get_account(),
                self.get_provider(),
                self.get_config().get_token_address("USDC")
            )
            print(f"Баланс: {utils.from_usdc_to_usd(usdc_balance)} USDC")

            portion = usdc_balance
            print(f"Будет проведён весь баланс ({utils.from_usdc_to_usd(portion)} USDC)")

            pool_addr = self.get_pool(
                "USDC",
                "WETH"
            )

            if pool_addr != utils.ZERO_ADDRESS:
                min_out = self.get_min_out(
                    pool_addr,
                    "USDC",
                    portion
                )

                steps = [{
                    "pool": pool_addr,
                    "data": abi.encode(
                        [
                            "address",
                            "address",
                            "uint8"
                        ],
                        [
                            self.get_config().get_token_address("USDC"),
                            self.get_account().address,
                            1
                        ]
                    ),
                    "callback": utils.ZERO_ADDRESS,
                    "callbackData": "0x"
                }]

                paths = [{
                    "steps": steps,
                    "tokenIn": self.get_config().get_token_address("USDC"),
                    "amountIn": portion
                }]

                if not self.has_enough_allowance(
                    self.contract.address,
                    "USDC",
                    portion
                ):
                    if self.approve(
                        self.contract.address,
                        "USDC",
                        portion
                    ):
                        current_gas_price = utils.get_gas_gwei()
                        if current_gas_price > self.get_config().get_max_gwei():
                            print(f"[SyncSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                                  f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                                  f"• текущая цена – {current_gas_price} GWei\n")
                            return

                        tx_data = {
                            "from": self.get_account().address,
                            "value": 0,
                            "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address),
                            "gasPrice": self.get_provider().eth.gas_price
                        }

                        deadline = int(time.time()) + 1800

                        gas = 0
                        while gas == 0:
                            try:
                                gas = self.contract.functions.swap(
                                    paths,
                                    min_out,
                                    deadline
                                ).estimate_gas(tx_data)
                            except ContractLogicError:
                                print(
                                    f"[SyncSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                    f"Будет произведена попытка просчёта снова.\n")

                                min_out = self.get_min_out(
                                    pool_addr,
                                    "WETH",
                                    portion
                                )

                        tx_data["gas"] = gas

                        swap_tx = self.contract.functions.swap(
                            paths,
                            min_out,
                            deadline
                        ).build_transaction(tx_data)

                        print(f"Адрес {self.get_account().address}: swap-операция USDC -> ETH\n"
                              f"• на входе {utils.from_usdc_to_usd(portion)} USDC\n"
                              f"• на выходе {self.get_provider().from_wei(min_out, 'ether')} ETH")

                        rand_sleep = self.get_config().get_random_tx_sleep()
                        print(f"\"Спим\" {rand_sleep} секунд...")
                        time.sleep(rand_sleep)

                        signed = self.get_account().sign_transaction(swap_tx)
                        try:
                            sent_tx = self.get_provider().eth.send_raw_transaction(signed.rawTransaction)
                        except ValueError:
                            print(f"Адрес {self.get_account().address}: недостаточно баланса ETH для транзакции!\n")
                            return

                        receipt = self.get_provider().eth.wait_for_transaction_receipt(sent_tx)

                        status = receipt.get("status")
                        if status == 1:
                            print(f"Адрес {self.get_account().address}: транзакция успешна!\n"
                                  f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
                        else:
                            print(f"Адрес {self.get_account().address}: произошла ошибка при выполнении транзакции!\n"
                                  f"• хэш транзакции: {receipt['transactionHash'].hex()}\n",
                                  file=sys.stderr
                                  )
                else:
                    current_gas_price = utils.get_gas_gwei()
                    if current_gas_price > self.get_config().get_max_gwei():
                        print(f"[SyncSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                              f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                              f"• текущая цена – {current_gas_price} GWei\n")
                        return

                    tx_data = {
                        "from": self.get_account().address,
                        "value": 0,
                        "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address),
                        "gasPrice": self.get_provider().eth.gas_price
                    }

                    deadline = int(time.time()) + 1800

                    gas = 0
                    while gas == 0:
                        try:
                            gas = self.contract.functions.swap(
                                paths,
                                min_out,
                                deadline
                            ).estimate_gas(tx_data)
                        except ContractLogicError:
                            print(
                                f"[SyncSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                f"Будет произведена попытка просчёта снова.\n")

                            min_out = self.get_min_out(
                                pool_addr,
                                "WETH",
                                portion
                            )

                    tx_data["gas"] = gas

                    swap_tx = self.contract.functions.swap(
                        paths,
                        min_out,
                        deadline
                    ).build_transaction(tx_data)

                    print(f"Адрес {self.get_account().address}: swap-операция USDC -> ETH\n"
                          f"• на входе {utils.from_usdc_to_usd(portion)} USDC\n"
                          f"• на выходе {self.get_provider().from_wei(min_out, 'ether')} ETH")

                    rand_sleep = self.get_config().get_random_tx_sleep()
                    print(f"\"Спим\" {rand_sleep} секунд...")
                    time.sleep(rand_sleep)

                    signed = self.get_account().sign_transaction(swap_tx)
                    try:
                        sent_tx = self.get_provider().eth.send_raw_transaction(signed.rawTransaction)
                    except ValueError:
                        print(f"Адрес {self.get_account().address}: недостаточно баланса ETH для транзакции!\n")
                        return

                    receipt = self.get_provider().eth.wait_for_transaction_receipt(sent_tx)

                    status = receipt.get("status")
                    if status == 1:
                        print(f"Адрес {self.get_account().address}: транзакция успешна!\n"
                              f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
                    else:
                        print(f"Адрес {self.get_account().address}: произошла ошибка при выполнении транзакции!\n"
                              f"• хэш транзакции: {receipt['transactionHash'].hex()}\n",
                              file=sys.stderr
                              )
            else:
                print(f"Адрес {self.get_account().address}: произошла ошибка при получении данных из пула!\n"
                      f"(был получен нулевой адрес пула – {utils.ZERO_ADDRESS})\n")
        elif self.o_id == utils.SWAP_USDC_USDT:
            usdc_balance = utils.get_token_balance(
                self.get_account(),
                self.get_provider(),
                self.get_config().get_token_address("USDC")
            )
            print(f"Баланс: {utils.from_usdc_to_usd(usdc_balance)} USDC")

            portion = usdc_balance
            print(f"Будет проведён весь баланс ({utils.from_usdc_to_usd(portion)} USDC)")

            pool_addr = self.get_pool(
                "USDC",
                "USDT"
            )

            if pool_addr != utils.ZERO_ADDRESS:
                min_out = self.get_min_out(
                    pool_addr,
                    "USDC",
                    portion
                )

                steps = [{
                    "pool": pool_addr,
                    "data": abi.encode(
                        [
                            "address",
                            "address",
                            "uint8"
                        ],
                        [
                            self.get_config().get_token_address("USDC"),
                            self.get_account().address,
                            1
                        ]
                    ),
                    "callback": utils.ZERO_ADDRESS,
                    "callbackData": "0x"
                }]

                paths = [{
                    "steps": steps,
                    "tokenIn": self.get_config().get_token_address("USDC"),
                    "amountIn": portion
                }]

                if not self.has_enough_allowance(
                    self.contract.address,
                    "USDC",
                    portion
                ):
                    if self.approve(
                        self.contract.address,
                        "USDC",
                        portion
                    ):
                        current_gas_price = utils.get_gas_gwei()
                        if current_gas_price > self.get_config().get_max_gwei():
                            print(f"[SyncSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                                  f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                                  f"• текущая цена – {current_gas_price} GWei\n")
                            return

                        tx_data = {
                            "from": self.get_account().address,
                            "value": 0,
                            "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address),
                            "gasPrice": self.get_provider().eth.gas_price
                        }

                        deadline = int(time.time()) + 1800

                        gas = 0
                        while gas == 0:
                            try:
                                gas = self.contract.functions.swap(
                                    paths,
                                    min_out,
                                    deadline
                                ).estimate_gas(tx_data)
                            except ContractLogicError:
                                print(
                                    f"[SyncSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                    f"Будет произведена попытка просчёта снова.\n")

                                min_out = self.get_min_out(
                                    pool_addr,
                                    "USDC",
                                    portion
                                )

                        tx_data["gas"] = gas

                        swap_tx = self.contract.functions.swap(
                            paths,
                            min_out,
                            deadline
                        ).build_transaction(tx_data)

                        print(f"Адрес {self.get_account().address}: swap-операция USDC -> USDT\n"
                              f"• на входе {utils.from_usdc_to_usd(portion)} USDC\n"
                              f"• на выходе {utils.from_usdc_to_usd(min_out)} USDT")

                        rand_sleep = self.get_config().get_random_tx_sleep()
                        print(f"\"Спим\" {rand_sleep} секунд...")
                        time.sleep(rand_sleep)

                        signed = self.get_account().sign_transaction(swap_tx)
                        try:
                            sent_tx = self.get_provider().eth.send_raw_transaction(signed.rawTransaction)
                        except ValueError:
                            print(f"Адрес {self.get_account().address}: недостаточно баланса ETH для транзакции!\n")
                            return

                        receipt = self.get_provider().eth.wait_for_transaction_receipt(sent_tx)

                        status = receipt.get("status")
                        if status == 1:
                            print(f"Адрес {self.get_account().address}: транзакция успешна!\n"
                                  f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
                        else:
                            print(f"Адрес {self.get_account().address}: произошла ошибка при выполнении транзакции!\n"
                                  f"• хэш транзакции: {receipt['transactionHash'].hex()}\n",
                                  file=sys.stderr
                                  )
                else:
                    current_gas_price = utils.get_gas_gwei()
                    if current_gas_price > self.get_config().get_max_gwei():
                        print(f"[SyncSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                              f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                              f"• текущая цена – {current_gas_price} GWei\n")
                        return

                    tx_data = {
                        "from": self.get_account().address,
                        "value": 0,
                        "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address),
                        "gasPrice": self.get_provider().eth.gas_price
                    }

                    deadline = int(time.time()) + 1800

                    gas = 0
                    while gas == 0:
                        try:
                            gas = self.contract.functions.swap(
                                paths,
                                min_out,
                                deadline
                            ).estimate_gas(tx_data)
                        except ContractLogicError:
                            print(
                                f"[SyncSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                f"Будет произведена попытка просчёта снова.\n")

                            min_out = self.get_min_out(
                                pool_addr,
                                "USDC",
                                portion
                            )

                    tx_data["gas"] = gas

                    swap_tx = self.contract.functions.swap(
                        paths,
                        min_out,
                        deadline
                    ).build_transaction(tx_data)

                    print(f"Адрес {self.get_account().address}: swap-операция USDC -> USDT\n"
                          f"• на входе {utils.from_usdc_to_usd(portion)} USDC\n"
                          f"• на выходе {utils.from_usdc_to_usd(min_out)} USDT")

                    rand_sleep = self.get_config().get_random_tx_sleep()
                    print(f"\"Спим\" {rand_sleep} секунд...")
                    time.sleep(rand_sleep)

                    signed = self.get_account().sign_transaction(swap_tx)
                    try:
                        sent_tx = self.get_provider().eth.send_raw_transaction(signed.rawTransaction)
                    except ValueError:
                        print(f"Адрес {self.get_account().address}: недостаточно баланса ETH для транзакции!\n")
                        return

                    receipt = self.get_provider().eth.wait_for_transaction_receipt(sent_tx)

                    status = receipt.get("status")
                    if status == 1:
                        print(f"Адрес {self.get_account().address}: транзакция успешна!\n"
                              f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
                    else:
                        print(f"Адрес {self.get_account().address}: произошла ошибка при выполнении транзакции!\n"
                              f"• хэш транзакции: {receipt['transactionHash'].hex()}\n",
                              file=sys.stderr
                              )
            else:
                print(f"Адрес {self.get_account().address}: произошла ошибка при получении данных из пула!\n"
                      f"(был получен нулевой адрес пула – {utils.ZERO_ADDRESS})\n")
        elif self.o_id == utils.SWAP_USDT_USDC:
            usdt_balance = utils.get_token_balance(
                self.get_account(),
                self.get_provider(),
                self.get_config().get_token_address("USDT")
            )
            print(f"Баланс: {utils.from_usdc_to_usd(usdt_balance)} USDT")

            portion = usdt_balance
            print(f"Будет проведён весь баланс ({utils.from_usdc_to_usd(portion)} USDT)")

            pool_addr = self.get_pool(
                "USDT",
                "USDC"
            )

            if pool_addr != utils.ZERO_ADDRESS:
                min_out = self.get_min_out(
                    pool_addr,
                    "USDT",
                    portion
                )

                steps = [{
                    "pool": pool_addr,
                    "data": abi.encode(
                        [
                            "address",
                            "address",
                            "uint8"
                        ],
                        [
                            self.get_config().get_token_address("USDT"),
                            self.get_account().address,
                            1
                        ]
                    ),
                    "callback": utils.ZERO_ADDRESS,
                    "callbackData": "0x"
                }]

                paths = [{
                    "steps": steps,
                    "tokenIn": self.get_config().get_token_address("USDT"),
                    "amountIn": portion
                }]

                if not self.has_enough_allowance(
                        self.contract.address,
                        "USDT",
                        portion
                ):
                    if self.approve(
                            self.contract.address,
                            "USDT",
                            portion
                    ):
                        current_gas_price = utils.get_gas_gwei()
                        if current_gas_price > self.get_config().get_max_gwei():
                            print(f"[SyncSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                                  f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                                  f"• текущая цена – {current_gas_price} GWei\n")
                            return

                        tx_data = {
                            "from": self.get_account().address,
                            "value": 0,
                            "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address),
                            "gasPrice": self.get_provider().eth.gas_price
                        }

                        deadline = int(time.time()) + 1800

                        gas = 0
                        while gas == 0:
                            try:
                                gas = self.contract.functions.swap(
                                    paths,
                                    min_out,
                                    deadline
                                ).estimate_gas(tx_data)
                            except ContractLogicError:
                                print(
                                    f"[SyncSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                    f"Будет произведена попытка просчёта снова.\n")

                                min_out = self.get_min_out(
                                    pool_addr,
                                    "USDT",
                                    portion
                                )

                        tx_data["gas"] = gas

                        swap_tx = self.contract.functions.swap(
                            paths,
                            min_out,
                            deadline
                        ).build_transaction(tx_data)

                        print(f"Адрес {self.get_account().address}: swap-операция USDT -> USDC\n"
                              f"• на входе {utils.from_usdc_to_usd(portion)} USDT\n"
                              f"• на выходе {utils.from_usdc_to_usd(min_out)} USDC")

                        rand_sleep = self.get_config().get_random_tx_sleep()
                        print(f"\"Спим\" {rand_sleep} секунд...")
                        time.sleep(rand_sleep)

                        signed = self.get_account().sign_transaction(swap_tx)
                        try:
                            sent_tx = self.get_provider().eth.send_raw_transaction(signed.rawTransaction)
                        except ValueError:
                            print(f"Адрес {self.get_account().address}: недостаточно баланса ETH для транзакции!\n")
                            return

                        receipt = self.get_provider().eth.wait_for_transaction_receipt(sent_tx)

                        status = receipt.get("status")
                        if status == 1:
                            print(f"Адрес {self.get_account().address}: транзакция успешна!\n"
                                  f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
                        else:
                            print(f"Адрес {self.get_account().address}: произошла ошибка при выполнении транзакции!\n"
                                  f"• хэш транзакции: {receipt['transactionHash'].hex()}\n",
                                  file=sys.stderr
                                  )
                else:
                    current_gas_price = utils.get_gas_gwei()
                    if current_gas_price > self.get_config().get_max_gwei():
                        print(f"[SyncSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                              f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                              f"• текущая цена – {current_gas_price} GWei\n")
                        return

                    tx_data = {
                        "from": self.get_account().address,
                        "value": 0,
                        "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address),
                        "gasPrice": self.get_provider().eth.gas_price
                    }

                    deadline = int(time.time()) + 1800

                    gas = 0
                    while gas == 0:
                        try:
                            gas = self.contract.functions.swap(
                                paths,
                                min_out,
                                deadline
                            ).estimate_gas(tx_data)
                        except ContractLogicError:
                            print(
                                f"[SyncSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                f"Будет произведена попытка просчёта снова.\n")

                            min_out = self.get_min_out(
                                pool_addr,
                                "USDC",
                                portion
                            )

                    tx_data["gas"] = gas

                    swap_tx = self.contract.functions.swap(
                        paths,
                        min_out,
                        deadline
                    ).build_transaction(tx_data)

                    print(f"Адрес {self.get_account().address}: swap-операция USDT -> USDC\n"
                          f"• на входе {utils.from_usdc_to_usd(portion)} USDT\n"
                          f"• на выходе {utils.from_usdc_to_usd(min_out)} USDC")

                    rand_sleep = self.get_config().get_random_tx_sleep()
                    print(f"\"Спим\" {rand_sleep} секунд...")
                    time.sleep(rand_sleep)

                    signed = self.get_account().sign_transaction(swap_tx)
                    try:
                        sent_tx = self.get_provider().eth.send_raw_transaction(signed.rawTransaction)
                    except ValueError:
                        print(f"Адрес {self.get_account().address}: недостаточно баланса ETH для транзакции!\n")
                        return

                    receipt = self.get_provider().eth.wait_for_transaction_receipt(sent_tx)

                    status = receipt.get("status")
                    if status == 1:
                        print(f"Адрес {self.get_account().address}: транзакция успешна!\n"
                              f"• хэш транзакции: {receipt['transactionHash'].hex()}\n")
                    else:
                        print(f"Адрес {self.get_account().address}: произошла ошибка при выполнении транзакции!\n"
                              f"• хэш транзакции: {receipt['transactionHash'].hex()}\n",
                              file=sys.stderr
                              )
            else:
                print(f"Адрес {self.get_account().address}: произошла ошибка при получении данных из пула!\n"
                      f"(был получен нулевой адрес пула – {utils.ZERO_ADDRESS})\n")

    def get_pool(
            self,
            from_token: str,
            to_token: str
    ):
        contract = self.get_provider().eth.contract(
            address=self.get_config().get_contract_address(
                "SyncSwap",
                contract_type="classicPool"
            ),
            abi=self.get_config().get_contract_abi(
                "SyncSwap",
                abi_type="classicPool"
            )
        )

        pool_address = contract.functions.getPool(
            self.get_config().get_token_address(from_token),
            self.get_config().get_token_address(to_token)
        ).call()

        return self.get_provider().to_checksum_address(pool_address)

    def get_min_out(
            self,
            pool_address: ChecksumAddress,
            from_token: str,
            amount: int):
        pool_contract = self.get_provider().eth.contract(
            address=pool_address,
            abi=self.get_config().get_contract_abi("SyncSwap", abi_type="classicPoolData")
        )
        min_amount_out = pool_contract.functions.getAmountOut(
            self.get_config().get_token_address(from_token),
            amount,
            self.get_account().address
        ).call()
        return int(min_amount_out - (min_amount_out / 100 * self.get_config().get_slippage("SyncSwap")))
