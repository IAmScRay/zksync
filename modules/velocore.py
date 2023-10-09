import random
import sys
import time

from eth_account.signers.local import LocalAccount
from web3.exceptions import ContractLogicError

import utils
from config import Configuration
from modules.module import Module


class Velocore(Module):

    def __init__(
            self,
            w3_url: str,
            proxy: str,
            account: LocalAccount,
            config: Configuration
    ):
        super().__init__(w3_url, proxy, account, config)

        self.contract = self.get_provider().eth.contract(
            address=config.get_contract_address("Velocore"),
            abi=config.get_contract_abi("Velocore")
        )

        self.o_id = 0

    def get_id(self) -> int:
        return self.get_config().get_project_id("Velocore")

    def run(self) -> None:
        rand_op = random.randint(1, 2)
        if rand_op == 1:  # ETH -> USDC
            print(f"[Velocore] Адрес {self.get_account().address}: будет проведена swap-операция ETH -> USDC")
            self.o_id = utils.SWAP_ETH_USDC
        else:
            print(f"[Velocore] Адрес {self.get_account().address}: будет проведена swap-операция USDC -> ETH")
            self.o_id = utils.SWAP_USDC_ETH

        if utils.get_token_balance(
            self.get_account(),
            self.get_provider(),
            self.get_config().get_token_address("USDC")
        ) < utils.from_usd_to_usdc(1.0) and self.o_id == utils.SWAP_USDC_ETH:
            print(f"Адрес {self.get_account().address}: недостаточно баланса для операции USDC -> ETH!\n"
                  f"Будет проведена swap-операция ETH -> USDC")
            self.o_id = utils.SWAP_ETH_USDC

        if self.o_id == utils.SWAP_ETH_USDC:
            eth_balance = self.get_provider().eth.get_balance(self.account.address, "latest")
            print(f"Баланс: {self.get_provider().from_wei(eth_balance, 'ether')} ETH")

            rand_portion = random.randint(20, 25)
            portion = eth_balance // 100 * rand_portion
            print(f"Будет проведено {rand_portion}% от баланса ({self.get_provider().from_wei(portion, 'ether')} ETH)")

            min_out = self.get_min_out(
                "WETH",
                "USDC",
                portion
            )

            current_gas_price = utils.get_gas_gwei()
            if current_gas_price > self.get_config().get_max_gwei():
                print(f"[Velocore] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
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

            gas = 0
            while gas == 0:
                try:
                    gas = self.contract.functions.swapExactETHForTokens(
                        min_out,
                        [
                            [
                                self.get_config().get_token_address("WETH"),
                                self.get_config().get_token_address("USDC"),
                                False
                            ]
                        ],
                        self.get_account().address,
                        deadline
                    ).estimate_gas(tx_data)
                except ContractLogicError:
                    print(f"[Velocore] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                          f"Будет произведена попытка просчёта снова.\n")

                    min_out = self.get_min_out(
                        "WETH",
                        "USDC",
                        portion
                    )

            tx_data["gas"] = gas

            swap_tx = self.contract.functions.swapExactETHForTokens(
                min_out,
                [
                    [
                        self.get_config().get_token_address("WETH"),
                        self.get_config().get_token_address("USDC"),
                        False
                    ]
                ],
                self.get_account().address,
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
                print(f"[Velocore] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                      f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                      f"• текущая цена – {current_gas_price} GWei\n")
                return

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
                            gas = self.contract.functions.swapExactTokensForETH(
                                portion,
                                min_out,
                                [
                                    [
                                        self.get_config().get_token_address("USDC"),
                                        self.get_config().get_token_address("WETH"),
                                        False
                                    ]
                                ],
                                self.get_account().address,
                                deadline
                            ).estimate_gas(tx_data)
                        except ContractLogicError:
                            print(
                                f"[Velocore] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                                f"Будет произведена попытка просчёта снова.\n")

                            min_out = self.get_min_out(
                                "USDC",
                                "WETH",
                                portion
                            )

                    tx_data["gas"] = gas

                    swap_tx = self.contract.functions.swapExactTokensForETH(
                        portion,
                        min_out,
                        [
                            [
                                self.get_config().get_token_address("USDC"),
                                self.get_config().get_token_address("WETH"),
                                False
                            ]
                        ],
                        self.get_account().address,
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
                        gas = self.contract.functions.swapExactTokensForETH(
                            portion,
                            min_out,
                            [
                                [
                                    self.get_config().get_token_address("USDC"),
                                    self.get_config().get_token_address("WETH"),
                                    False
                                ]
                            ],
                            self.get_account().address,
                            deadline
                        ).estimate_gas(tx_data)
                    except ContractLogicError:
                        print(f"[Velocore] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                            f"Будет произведена попытка просчёта снова.\n")

                        min_out = self.get_min_out(
                            "USDC",
                            "WETH",
                            portion
                        )

                tx_data["gas"] = gas

                swap_tx = self.contract.functions.swapExactTokensForETH(
                    portion,
                    min_out,
                    [
                        [
                            self.get_config().get_token_address("USDC"),
                            self.get_config().get_token_address("WETH"),
                            False
                        ]
                    ],
                    self.get_account().address,
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

    def get_min_out(
            self,
            from_token: str,
            to_token: str,
            amount: int
    ) -> int:
        token_from_address = self.get_config().get_token_address(from_token)
        token_to_address = self.get_config().get_token_address(to_token)

        amount_out = self.contract.functions.getAmountOut(
            amount,
            token_from_address,
            token_to_address
        ).call()

        return int(amount_out[0] - amount_out[0] / 100 * self.get_config().get_slippage("Velocore"))
