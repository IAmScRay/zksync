import sys
import time

from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.exceptions import ContractLogicError

import utils
from config import Configuration
from modules.module import Module


class TevaEra(Module):

    def __init__(
            self,
            w3_url: str,
            proxy: str,
            account: LocalAccount,
            config: Configuration
    ):
        super().__init__(w3_url, proxy, account, config)

        self.id_contract = self.get_provider().eth.contract(
            address=config.get_contract_address("TevaEra", contract_type="id"),
            abi=config.get_contract_abi("TevaEra", abi_type="id")
        )

        self.nft_contract = self.get_provider().eth.contract(
            address=config.get_contract_address("TevaEra", contract_type="nft"),
            abi=config.get_contract_abi("TevaEra", abi_type="nft")
        )

    def get_id(self) -> int:
        return self.get_config().get_project_id("TevaEra")

    def run(self):
        print(f"Адрес {self.get_account().address}: будут созданы Citizen ID и NFT на TevaEra")

        if not self.has_id():
            current_gas_price = utils.get_gas_gwei()
            if current_gas_price > self.get_config().get_max_gwei():
                print(f"[TevaEra] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                      f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                      f"• текущая цена – {current_gas_price} GWei\n")
                return

            tx_data = {
                "from": self.get_account().address,
                "value": self.get_provider().to_wei(0.0003, "ether"),
                "gasPrice": self.get_provider().eth.gas_price,
                "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
            }

            gas = 0
            while gas == 0:
                try:
                    gas = self.id_contract.functions.mintCitizenId().estimate_gas(tx_data)
                except ContractLogicError:
                    print(f"[TevaEra] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                          f"Будет произведена попытка просчёта снова.\n")

                    time.sleep(3)

            tx_data["gas"] = gas

            id_tx = self.id_contract.functions.mintCitizenId().build_transaction(tx_data)

            print(f"Адрес {self.get_account().address}: будет создан Citizen ID\n"
                  f"• единоразовая плата: 0.0003 ETH")

            rand_sleep = self.get_config().get_random_tx_sleep()
            print(f"\"Спим\" {rand_sleep} секунд...")

            time.sleep(rand_sleep)

            signed = self.get_account().sign_transaction(id_tx)
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
            print(f"Адрес {self.get_account().address}: Citizen ID уже имеется!\n")

        if not self.has_nft():
            current_gas_price = utils.get_gas_gwei()
            if current_gas_price > self.get_config().get_max_gwei():
                print(f"[TevaEra] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                      f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                      f"• текущая цена – {current_gas_price} GWei\n")
                return

            tx_data = {
                "from": self.get_account().address,
                "value": 0,
                "gasPrice": self.get_provider().eth.gas_price,
                "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
            }

            gas = 0
            while gas == 0:
                try:
                    gas = self.nft_contract.functions.mint().estimate_gas(tx_data)
                except ContractLogicError:
                    print(f"[TevaEra] Адрес {self.get_account().address}: ошибка при определении лимита газа!\n"
                          f"Будет произведена попытка просчёта снова.\n")

                    time.sleep(3)

            tx_data["gas"] = gas

            nft_tx = self.nft_contract.functions.mint().build_transaction(tx_data)

            print(f"Адрес {self.get_account().address}: будет создан 1 NFT\n")

            rand_sleep = self.get_config().get_random_tx_sleep()
            print(f"\"Спим\" {rand_sleep} секунд...")

            time.sleep(rand_sleep)

            signed = self.get_account().sign_transaction(nft_tx)
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
            print(f"Адрес {self.get_account().address}: NFT уже имеется!\n")

    def has_id(self) -> bool:
        id_balance = self.id_contract.functions.balanceOf(
            self.get_account().address
        ).call()

        return id_balance > 0

    def has_nft(self) -> bool:
        nft_balance = self.nft_contract.functions.balanceOf(
            self.get_account().address
        ).call()

        return nft_balance > 0

