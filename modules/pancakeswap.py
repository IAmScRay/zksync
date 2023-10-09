import random
import sys
import time

from eth_account.signers.local import LocalAccount
from web3.exceptions import ContractLogicError

import utils
from config import Configuration
from modules.module import Module


class PancakeSwap(Module):

    def __init__(
            self,
            w3_url: str,
            proxy: str,
            account: LocalAccount,
            config: Configuration,
            o_id: int = 0  # TODO: убрать после отработки!
    ):
        super().__init__(w3_url, proxy, account, config)

        self.contract = self.get_provider().eth.contract(
            address=config.get_contract_address("PancakeSwap"),
            abi=config.get_contract_abi("PancakeSwap")
        )

        self.o_id = o_id

    def get_id(self):
        return self.get_config().get_project_id("PancakeSwap")

    def run(self):
        if self.o_id == 0:
            rand_op = random.randint(1, 4)
            if rand_op == 1:
                print(f"[PancakeSwap] Адрес {self.get_account().address}: будет проведена swap-операция USDC -> USDT")
                self.o_id = utils.SWAP_USDC_USDT
            elif rand_op == 2:
                print(f"[PancakeSwap] Адрес {self.get_account().address}: будет проведена swap-операция ETH -> USDC")
                self.o_id = utils.SWAP_ETH_USDC
            elif rand_op == 3:
                print(f"[PancakeSwap] Адрес {self.get_account().address}: будет проведена swap-операция USDT -> USDC")
                self.o_id = utils.SWAP_USDT_USDC
            elif rand_op == 4:
                print(f"[PancakeSwap] Адрес {self.get_account().address}: будет проведена swap-операция USDC -> ETH")
                self.o_id = utils.SWAP_USDC_ETH
        else:  # TODO: убрать ВЕСЬ блок после отработки!
            if (
                    self.o_id == utils.SWAP_USDT_USDC and
                    utils.get_token_balance(
                        self.get_account(),
                        self.get_provider(),
                        self.get_config().get_token_address("USDT")
                    ) < utils.from_usd_to_usdc(1.0)
            ):
                print(f"[PancakeSwap] Адрес {self.get_account().address}: недостаточно баланса для проведения операции "
                      f"USDT -> USDC!")
                print(f"Будет проведена операция USDC -> ETH")
                self.o_id = utils.SWAP_USDC_ETH
            if (
                    self.o_id == utils.SWAP_USDC_ETH and
                    utils.get_token_balance(
                        self.get_account(),
                        self.get_provider(),
                        self.get_config().get_token_address("USDC")
                    ) < utils.from_usd_to_usdc(1.0)
            ):
                print(
                    f"[PancakeSwap] Адрес {self.get_account().address}: невозможно провести операции над USDC / USDT!")
                return

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

            min_out = self.get_min_out(
                "WETH",
                "USDC",
                portion
            )

            current_gas_price = utils.get_gas_gwei()
            if current_gas_price > self.get_config().get_max_gwei():
                print(f"[PancakeSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                      f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                      f"• текущая цена – {current_gas_price} GWei\n")
                return

            tx_data = {
                "from": self.get_account().address,
                "value": portion,
                "gasPrice": self.get_provider().eth.gas_price,
                "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
            }

            deadline = int(time.time()) + 1800

            transaction_data = self.contract.encodeABI(
                fn_name="exactInputSingle",
                args=[(
                    self.get_config().get_token_address("WETH"),
                    self.get_config().get_token_address("USDC"),
                    500,
                    self.get_account().address,
                    portion,
                    min_out,
                    0
                )]
            )

            gas = 0
            while gas == 0:
                try:
                    gas = self.contract.functions.multicall(
                        deadline,
                        [transaction_data]
                    ).estimate_gas(tx_data)
                except ContractLogicError:
                    print(f"[PancakeSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                          f"Будет произведена попытка просчёта снова.\n")

                    min_out = self.get_min_out(
                        "WETH",
                        "USDC",
                        portion
                    )

                    transaction_data = self.contract.encodeABI(
                        fn_name="exactInputSingle",
                        args=[(
                            self.get_config().get_token_address("WETH"),
                            self.get_config().get_token_address("USDC"),
                            500,
                            self.get_account().address,
                            portion,
                            min_out,
                            0
                        )]
                    )

            tx_data["gas"] = gas

            swap_tx = self.contract.functions.multicall(
                deadline,
                [transaction_data]
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
        elif self.o_id == utils.SWAP_USDC_ETH:
            usdc_balance = utils.get_token_balance(
                self.get_account(),
                self.get_provider(),
                self.get_config().get_token_address("USDC")
            )
            print(f"Баланс: {utils.from_usdc_to_usd(usdc_balance)} USDC")

            portion = usdc_balance
            print(f"Будет проведён весь баланс ({utils.from_usdc_to_usd(portion)} USDC)")

            min_out = self.get_min_out(
                "USDC",
                "WETH",
                portion
            )

            current_gas_price = utils.get_gas_gwei()
            if current_gas_price > self.get_config().get_max_gwei():
                print(f"[PancakeSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                      f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                      f"• текущая цена – {current_gas_price} GWei\n")
                return

            transaction_data = self.contract.encodeABI(
                fn_name="exactInputSingle",
                args=[(
                    self.get_config().get_token_address("USDC"),
                    self.get_config().get_token_address("WETH"),
                    500,
                    self.get_provider().to_checksum_address(utils.PANCAKE_ZERO_ADDRESS),
                    portion,
                    min_out,
                    0
                )]
            )

            unwrap_data = self.contract.encodeABI(
                fn_name="unwrapWETH9",
                args=[
                    min_out,
                    self.get_account().address
                ]
            )

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
                    tx_data = {
                        "from": self.get_account().address,
                        "value": 0,
                        "gasPrice": self.get_provider().eth.gas_price,
                        "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
                    }

                    deadline = int(time.time()) + 1800

                    gas = 0
                    while gas == 0:
                        try:
                            gas = self.contract.functions.multicall(
                                deadline,
                                [transaction_data, unwrap_data]
                            ).estimate_gas(tx_data)
                        except ContractLogicError:
                            print(
                                f"[PancakeSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                f"Будет произведена попытка просчёта снова.\n")

                            min_out = self.get_min_out(
                                "USDC",
                                "WETH",
                                portion
                            )

                            transaction_data = self.contract.encodeABI(
                                fn_name="exactInputSingle",
                                args=[(
                                    self.get_config().get_token_address("USDC"),
                                    self.get_config().get_token_address("WETH"),
                                    500,
                                    self.get_provider().to_checksum_address(utils.PANCAKE_ZERO_ADDRESS),
                                    portion,
                                    min_out,
                                    0
                                )]
                            )

                            unwrap_data = self.contract.encodeABI(
                                fn_name="unwrapWETH9",
                                args=[
                                    min_out,
                                    self.get_account().address
                                ]
                            )

                    tx_data["gas"] = gas

                    swap_tx = self.contract.functions.multicall(
                        deadline,
                        [transaction_data, unwrap_data]
                    ).build_transaction(tx_data)

                    print(f"Адрес {self.get_account().address}: swap-операция USDC -> ETH\n"
                          f"• на входе {utils.from_usdc_to_usd(portion)} USDC\n"
                          f"• на выходе {self.get_provider().from_wei(min_out, 'ether')} ETH")

                    rand_sleep = self.get_config().get_random_tx_sleep()
                    print(f"\"Спим\" {rand_sleep} секунд...")

                    time.sleep(rand_sleep)

                    signed = self.get_account().sign_transaction(swap_tx)
                    sent_tx = self.get_provider().eth.send_raw_transaction(signed.rawTransaction)

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
                tx_data = {
                    "from": self.get_account().address,
                    "value": 0,
                    "gasPrice": self.get_provider().eth.gas_price,
                    "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
                }

                deadline = int(time.time()) + 1800

                gas = 0
                while gas == 0:
                    try:
                        gas = self.contract.functions.multicall(
                            deadline,
                            [transaction_data, unwrap_data]
                        ).estimate_gas(tx_data)
                    except ContractLogicError:
                        print(
                            f"[PancakeSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                            f"Будет произведена попытка просчёта снова.\n")

                        min_out = self.get_min_out(
                            "USDC",
                            "WETH",
                            portion
                        )

                        transaction_data = self.contract.encodeABI(
                            fn_name="exactInputSingle",
                            args=[(
                                self.get_config().get_token_address("USDC"),
                                self.get_config().get_token_address("WETH"),
                                500,
                                self.get_provider().to_checksum_address(utils.PANCAKE_ZERO_ADDRESS),
                                portion,
                                min_out,
                                0
                            )]
                        )

                        unwrap_data = self.contract.encodeABI(
                            fn_name="unwrapWETH9",
                            args=[
                                min_out,
                                self.get_account().address
                            ]
                        )

                tx_data["gas"] = gas

                swap_tx = self.contract.functions.multicall(
                    deadline,
                    [transaction_data, unwrap_data]
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
        elif self.o_id == utils.SWAP_USDC_USDT:
            usdc_balance = utils.get_token_balance(
                self.get_account(),
                self.get_provider(),
                self.get_config().get_token_address("USDC")
            )
            print(f"Баланс: {utils.from_usdc_to_usd(usdc_balance)} USDC")

            portion = usdc_balance
            print(f"Будет проведён весь баланс ({utils.from_usdc_to_usd(portion)} USDC)")

            min_out = self.get_min_out(
                "USDC",
                "USDT",
                portion
            )

            current_gas_price = utils.get_gas_gwei()
            if current_gas_price > self.get_config().get_max_gwei():
                print(f"[PancakeSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                      f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                      f"• текущая цена – {current_gas_price} GWei\n")
                return

            transaction_data = self.contract.encodeABI(
                fn_name="exactInputSingle",
                args=[(
                    self.get_config().get_token_address("USDC"),
                    self.get_config().get_token_address("USDT"),
                    500,
                    self.get_account().address,
                    portion,
                    min_out,
                    0
                )]
            )

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
                    tx_data = {
                        "from": self.get_account().address,
                        "value": 0,
                        "gasPrice": self.get_provider().eth.gas_price,
                        "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
                    }

                    deadline = int(time.time()) + 1800

                    gas = 0
                    while gas == 0:
                        try:
                            gas = self.contract.functions.multicall(
                                deadline,
                                [transaction_data]
                            ).estimate_gas(tx_data)
                        except ContractLogicError:
                            print(
                                f"[PancakeSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                f"Будет произведена попытка просчёта снова.\n")

                            min_out = self.get_min_out(
                                "USDC",
                                "USDT",
                                portion
                            )

                            transaction_data = self.contract.encodeABI(
                                fn_name="exactInputSingle",
                                args=[(
                                    self.get_config().get_token_address("USDC"),
                                    self.get_config().get_token_address("USDT"),
                                    500,
                                    self.get_account().address,
                                    portion,
                                    min_out,
                                    0
                                )]
                            )

                    tx_data["gas"] = gas

                    swap_tx = self.contract.functions.multicall(
                        deadline,
                        [transaction_data]
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
                tx_data = {
                    "from": self.get_account().address,
                    "value": 0,
                    "gasPrice": self.get_provider().eth.gas_price,
                    "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
                }

                deadline = int(time.time()) + 1800

                gas = 0
                while gas == 0:
                    try:
                        gas = self.contract.functions.multicall(
                            deadline,
                            [transaction_data]
                        ).estimate_gas(tx_data)
                    except ContractLogicError:
                        print(
                            f"[PancakeSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                            f"Будет произведена попытка просчёта снова.\n")

                        min_out = self.get_min_out(
                            "USDC",
                            "USDT",
                            portion
                        )

                        transaction_data = self.contract.encodeABI(
                            fn_name="exactInputSingle",
                            args=[(
                                self.get_config().get_token_address("USDC"),
                                self.get_config().get_token_address("USDT"),
                                500,
                                self.get_account().address,
                                portion,
                                min_out,
                                0
                            )]
                        )

                tx_data["gas"] = gas

                swap_tx = self.contract.functions.multicall(
                    deadline,
                    [transaction_data]
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
        elif self.o_id == utils.SWAP_USDT_USDC:
            usdt_balance = utils.get_token_balance(
                self.get_account(),
                self.get_provider(),
                self.get_config().get_token_address("USDT")
            )
            print(f"Баланс: {utils.from_usdc_to_usd(usdt_balance)} USDT")

            portion = usdt_balance
            print(f"Будет проведён весь баланс ({utils.from_usdc_to_usd(portion)} USDT)")

            min_out = self.get_min_out(
                "USDT",
                "USDC",
                portion
            )

            current_gas_price = utils.get_gas_gwei()
            if current_gas_price > self.get_config().get_max_gwei():
                print(f"[PancakeSwap] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                      f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                      f"• текущая цена – {current_gas_price} GWei\n")
                return

            transaction_data = self.contract.encodeABI(
                fn_name="exactInputSingle",
                args=[(
                    self.get_config().get_token_address("USDT"),
                    self.get_config().get_token_address("USDC"),
                    500,
                    self.get_account().address,
                    portion,
                    min_out,
                    0
                )]
            )

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
                    tx_data = {
                        "from": self.get_account().address,
                        "value": 0,
                        "gasPrice": self.get_provider().eth.gas_price,
                        "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
                    }

                    deadline = int(time.time()) + 1800

                    gas = 0
                    while gas == 0:
                        try:
                            gas = self.contract.functions.multicall(
                                deadline,
                                [transaction_data]
                            ).estimate_gas(tx_data)
                        except ContractLogicError:
                            print(
                                f"[PancakeSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                f"Будет произведена попытка просчёта снова.\n")

                            min_out = self.get_min_out(
                                "USDT",
                                "USDC",
                                portion
                            )

                            transaction_data = self.contract.encodeABI(
                                fn_name="exactInputSingle",
                                args=[(
                                    self.get_config().get_token_address("USDT"),
                                    self.get_config().get_token_address("USDC"),
                                    500,
                                    self.get_account().address,
                                    portion,
                                    min_out,
                                    0
                                )]
                            )

                    tx_data["gas"] = gas

                    swap_tx = self.contract.functions.multicall(
                        deadline,
                        [transaction_data]
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
                tx_data = {
                    "from": self.get_account().address,
                    "value": 0,
                    "gasPrice": self.get_provider().eth.gas_price,
                    "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
                }

                deadline = int(time.time()) + 1800

                gas = 0
                while gas == 0:
                    try:
                        gas = self.contract.functions.multicall(
                            deadline,
                            [transaction_data]
                        ).estimate_gas(tx_data)
                    except ContractLogicError:
                        print(
                            f"[PancakeSwap] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                            f"Будет произведена попытка просчёта снова.\n")

                        min_out = self.get_min_out(
                            "USDT",
                            "USDC",
                            portion
                        )

                        transaction_data = self.contract.encodeABI(
                            fn_name="exactInputSingle",
                            args=[(
                                self.get_config().get_token_address("USDT"),
                                self.get_config().get_token_address("USDC"),
                                500,
                                self.get_account().address,
                                portion,
                                min_out,
                                0
                            )]
                        )

                tx_data["gas"] = gas

                swap_tx = self.contract.functions.multicall(
                    deadline,
                    [transaction_data]
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

    def get_min_out(
            self,
            from_token: str,
            to_token: str,
            amount: int
    ) -> int:
        quoter = self.get_provider().eth.contract(
            address=self.get_config().get_contract_address("PancakeSwap", "quoter"),
            abi=self.get_config().get_contract_abi("PancakeSwap", "quoter")
        )

        amount_out = quoter.functions.quoteExactInputSingle(
            (
                self.get_config().get_token_address(from_token),
                self.get_config().get_token_address(to_token),
                amount,
                500,
                0
            )
        ).call()

        return int(amount_out[0] - amount_out[0] / 100 * self.get_config().get_slippage("PancakeSwap"))
