import json

from wise_manager import WiseAccountManager

db_name = 'database.json'


def load_database() -> list[dict]:
    with open(db_name) as f:
        return json.loads(f.read())


def save_database(db_snapshot: list[dict]):
    with open(db_name, 'w') as f:
        f.write(json.dumps(db_snapshot))


def add_wise_account(wise_account: WiseAccountManager):
    db = load_database()
    db.append(wise_account.get_state())
    save_database(db)


def delete_wise_account_by_access_token(wise_access_token: str):
    db = load_database()

    for i, wise_state in enumerate(db):
        for name, state in wise_state.items():
            if state[0] == wise_access_token:
                db.pop(i)
                return save_database(db)

    raise Exception('Could not found such wise account')


def get_wise_account_by_name(name: str) -> WiseAccountManager:
    db = load_database()
    for wise_state in db:
        if name in wise_state.keys():
            return WiseAccountManager(name, *wise_state[name])
    raise Exception('Could not found such wise account')


def get_all_wise_accounts() -> list[WiseAccountManager]:
    db = load_database()
    wise_accounts = []
    for wise_state in db:
        for name, state in wise_state.items():
            try:
                wise_accounts.append(WiseAccountManager(name, *state))
            except Exception:
                pass
    return wise_accounts
