import random
import sys
import time

from eth_account.signers.local import LocalAccount

from config import Configuration
from modules.module import Module


class Dmail(Module):

    def __init__(
            self,
            w3_url: str,
            proxy: str,
            account: LocalAccount,
            config: Configuration
    ):
        super().__init__(w3_url, proxy, account, config)

        self.contract = self.get_provider().eth.contract(
            address=config.get_contract_address("Dmail", contract_type="contract"),
            abi=config.get_contract_abi("Dmail", abi_type="contract")
        )

    def get_id(self) -> int:
        return self.get_config().get_project_id("Dmail")

    def run(self):
        print(f"[Dmail] Адрес {self.get_account().address}: будет отправлено письмо по случайному адресу из списка\n")
        own_email = str(self.get_account().address).lower() + "@dmail.ai"

        email_list = list(self.get_config().get_additional("Dmail", "addresses"))
        random_email = random.choice(email_list)

        tx_data = {
            "from": self.get_account().address,
            "value": 0,
            "gasPrice": self.get_provider().eth.gas_price,
            "nonce": self.get_provider().eth.get_transaction_count(self.get_account().address)
        }

        gas = self.contract.functions.send_mail(
            own_email,
            random_email
        ).estimate_gas(tx_data)

        tx_data["gas"] = gas

        mail_tx = self.contract.functions.send_mail(
            own_email,
            random_email
        ).build_transaction(tx_data)

        print(f"Адрес {self.get_account().address}: отправка письма\n"
              f"• отправитель: {own_email}\n"
              f"• получатель: {random_email}\n")

        random_sleep = self.get_config().get_random_tx_sleep()
        print(f"\"Спим\" {random_sleep} секунд...")

        time.sleep(random_sleep)

        signed = self.get_account().sign_transaction(mail_tx)

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
