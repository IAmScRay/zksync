import sys
import time

from eth_account.signers.local import LocalAccount
from web3.exceptions import ContractLogicError

import utils
from config import Configuration
from modules.module import Module


class CrossChainNFT(Module):

    def __init__(
            self,
            w3_url: str,
            proxy: str,
            account: LocalAccount,
            config: Configuration
    ):
        super().__init__(w3_url, proxy, account, config)

        self.contract = self.get_provider().eth.contract(
            address=config.get_contract_address("CrossChainNFT", contract_type="contract"),
            abi=config.get_contract_abi("CrossChainNFT", abi_type="contract")
        )

    def get_id(self) -> int:
        return self.get_config().get_project_id("CrossChainNFT")

    def run(self):
        nft_balance = self.contract.functions.balanceOf(
            self.get_account().address
        ).call()

        if nft_balance > 0:
            print(f"[CrossChainNFT] Адрес {self.get_account().address}: NFT уже был создан!\n")
            return

        current_gas_price = utils.get_gas_gwei()
        if current_gas_price > self.get_config().get_max_gwei():
            print(f"[CrossChainNFT] Адрес {self.get_account().address}: слишком высокая цена за газ!\n"
                  f"• требуется цена {self.get_config().get_max_gwei()} GWei и ниже\n"
                  f"• текущая цена – {current_gas_price} GWei\n")
            return

        tx_data = {
            "from": self.get_account().address,
            "value": 0,
            "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address),
            "gasPrice": self.get_provider().eth.gas_price
        }

        gas = 0
        while gas == 0:
            try:
                gas = self.contract.functions.mint().estimate_gas(tx_data)
            except ContractLogicError:
                print(f"Адрес {self.get_account().address}: произошла ошибка при определении лимита газа!\n"
                      f"Будет произведено попытка просчёта снова.\n")

        tx_data["gas"] = gas

        print(f"Адрес {self.get_account().address}: будет создан 1 NFT")

        random_sleep = self.get_config().get_random_tx_sleep()
        print(f"\"Спим\" {random_sleep} секунд...")
        time.sleep(random_sleep)

        mint_tx = self.contract.functions.mint().build_transaction(tx_data)

        signed = self.get_account().sign_transaction(mint_tx)

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
            print(f"Адрес {self.get_account().address}: произошла ошибка во время"
                  f"выполнения транзакции!\n", file=sys.stderr)
