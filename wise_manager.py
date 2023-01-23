from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import Iterator

import requests
import enum

from concurrent.futures import ThreadPoolExecutor

UUID_GENERATOR_ROUTE = "https://www.uuidgenerator.net/api/guid"


def get_uuid() -> str:
    return requests.get(UUID_GENERATOR_ROUTE).text


class CurrencyType(enum.Enum):
    USD = 'USD'
    EUR = 'EUR'
    UAH = 'UAH'


class WiseRoutes:
    default_url = "https://api.transferwise.com/"
    get_all_balances = default_url + "v4/profiles/{profile_id}/balances?types=STANDARD"
    get_all_profiles = default_url + "v2/profiles"
    get_all_jars = default_url + "v4/profiles/{profile_id}/balances?types=SAVINGS"
    send_money_to_jar = default_url + "v2/profiles/{profile_id}/balance-movements"


class WiseAccountManager:
    def __init__(self,
                 name: str,
                 access_token: str,
                 balance_currency: CurrencyType,
                 jar_currency: CurrencyType):
        self.name = name
        self.access_token = access_token
        self.balance_currency = CurrencyType(balance_currency)
        self.jar_currency = CurrencyType(jar_currency)
        self._wise_session = requests.Session()
        self._default_headers = {'Authorization': f'Bearer {self.access_token}'}
        self._wise_session.headers.update(self._default_headers)
        try:
            self._profile_id = self.get_profile_id()
            self._balance_id = self.get_balance_id_by_currency(
                self.balance_currency)
            self._jar_id = self.get_jar_id_by_currency(self.jar_currency)
        except Exception:
            raise InvalidAccessTokenError

    def _prepare_headers(self, headers: dict[str, str]) -> dict[str, str]:
        headers.update(self._default_headers)
        return headers

    def get_profile_id(self) -> int:
        profiles_list: list[dict] = self._wise_session.get(
            WiseRoutes.get_all_profiles).json()
        first_profile = profiles_list[0]
        return first_profile['id']

    def get_all_balances(self) -> list[dict]:
        url = WiseRoutes.get_all_balances.format(profile_id=self._profile_id)
        all_balances: list[dict] = self._wise_session.get(url, timeout=1).json()
        return all_balances

    def get_balance_id_by_currency(self, currency: CurrencyType,
                                   all_balances: list[dict] = None) -> int:
        if all_balances is None:
            all_balances = self.get_all_balances()

        for balance in all_balances:
            if balance['currency'] == CurrencyType(currency).value:
                return balance['id']
        raise Exception("Could not find balance with such currency type")

    def get_jar_id_by_currency(self, currency: CurrencyType) -> int:
        url = WiseRoutes.get_all_jars.format(profile_id=self._profile_id)
        all_jars: list[dict] = self._wise_session.get(url).json()
        jar_by_currency = self.get_balance_id_by_currency(currency,
                                                          all_jars)
        return jar_by_currency

    def send_money_to_jar(self, amount: int, currency: CurrencyType) -> int:
        url = WiseRoutes.send_money_to_jar.format(profile_id=self._profile_id)
        payload = {
            "amount": {
                "value": amount,
                "currency": CurrencyType(currency).value
            },
            "sourceBalanceId": self._balance_id,
            "targetBalanceId": self._jar_id
        }
        idempotence_uuid = get_uuid()
        self._wise_session.headers.update(
            {"X-idempotence-uuid": idempotence_uuid})
        resp = self._wise_session.post(url, json=payload, timeout=2)
        return resp.status_code

    def get_amount_of_money_by_balance_id(self, balance_id: int) -> int:
        for balance in self.get_all_balances():
            if balance['id'] == balance_id:
                return balance['amount']['value']
        raise Exception("Could not find balance with such id")

    def get_state(self):

        return {
            self.name: (
                self.access_token,
                self.balance_currency.value,
                self.jar_currency.value)
        }


class InvalidAccessTokenError(Exception):
    pass


class WiseStateManager:
    def __init__(self):
        self.enabled_accounts: list[WiseAccountManager] = []
        self.disabled_accounts: list[WiseAccountManager] = []

    def add(self, wise_account: WiseAccountManager):
        self.disabled_accounts.append(wise_account)

    def enable(self, wise_access_token: str):
        account_index = self._get_account_index_by_access_token(
            wise_access_token, self.disabled_accounts)
        self.enabled_accounts.append(self.disabled_accounts.pop(account_index))

    def disable(self, wise_access_token: str):
        account_index = self._get_account_index_by_access_token(
            wise_access_token, self.enabled_accounts)
        self.disabled_accounts.append(self.enabled_accounts.pop(account_index))

    def delete(self, wise_access_token: str):
        try:
            acc_id = self._get_account_index_by_access_token(wise_access_token,
                                                             self.enabled_accounts)
            self.enabled_accounts.pop(acc_id)
        except Exception:
            acc_id = self._get_account_index_by_access_token(wise_access_token,
                                                             self.disabled_accounts)
            self.disabled_accounts.pop(acc_id)

    def act_money_transfer(self,
                           wise_account: WiseAccountManager
                           ) -> tuple[str, str, int]:
        default_success_code = 201
        try:
            account_balance = wise_account.get_amount_of_money_by_balance_id(
                wise_account._balance_id)
            if account_balance > 0:
                return wise_account.name, wise_account.access_token, wise_account.send_money_to_jar(
                    account_balance, wise_account.balance_currency)
            return wise_account.name, wise_account.access_token, default_success_code
        except Exception:
            return wise_account.name, wise_account.access_token, default_success_code

    def _get_account_index_by_access_token(self,
                                           access_token: str,
                                           accounts: list[WiseAccountManager]
                                           ) -> int:
        for i, acc in enumerate(accounts):
            if acc.access_token == access_token:
                return i
        raise Exception("Could not find account with such access token")
    def temp(self, try_, accs=None):
        executor = ThreadPoolExecutor(15)
        return executor.map(self.act_money_transfer, accs)

    def run(self) -> Iterator[tuple[str, str, int]]:
        temp_fu = partial(self.temp, accs=self.enabled_accounts[:int(len(self.enabled_accounts)/2)])
        with ProcessPoolExecutor() as executor:
            process_res = executor.map(temp_fu, [1])
            process_res = list(process_res)[0]
        executor = ThreadPoolExecutor(15)
        cur_process_res = executor.map(self.act_money_transfer, self.enabled_accounts[int(len(self.enabled_accounts)/2):])
        return list(process_res) + list(cur_process_res)
