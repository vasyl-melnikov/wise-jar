import typing

from typing import Literal

from fastapi import FastAPI, Form, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi_utils.tasks import repeat_every
from starlette.responses import HTMLResponse
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware

from db import get_all_wise_accounts, add_wise_account
from wise_manager import InvalidAccessTokenError
from wise_manager import WiseAccountManager, WiseStateManager, CurrencyType
from email_sender import MailSender


middleware = [
    Middleware(SessionMiddleware, secret_key='super-secret')
]
app = FastAPI(middleware=middleware)
templates = Jinja2Templates(directory="templates")
wise_state_manager = WiseStateManager()
mail_sender = MailSender("smtp-mail.outlook.com", 587, "wiseaccouns351322@outlook.com",
                         "wiseaccouns351322@outlook.com", "PQ!$#g2Ef@Qt@s3")


def flash(request: Request, message: typing.Any, category: str = "") -> None:
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append(
        {"message": message, "category": category})


def get_flashed_messages(request: Request):
    return request.session.pop(
        "_messages") if "_messages" in request.session else []


templates.env.globals['get_flashed_messages'] = get_flashed_messages


@app.on_event('startup')
def add_account_to_wise_state_manager():
    accounts = get_all_wise_accounts()
    for account in accounts:
        wise_state_manager.add(account)


@app.on_event('startup')
@repeat_every(seconds=10)
def execute_state_manager():
    default_email_to_send = 'olegysxd@gmail.com'
    results = wise_state_manager.run()

    for result in results:
        account_name, access_token, exec_res = result
        if exec_res == 201:
            continue
        elif exec_res == 401:
            subj = f'Authentication error'
            msg = f'Authentication error with such account: {account_name}\n' \
                  f'Please review your account credentials!'
            mail_sender.send_mail(subj, default_email_to_send, msg)
            wise_state_manager.disable(access_token)
        else:
            subj = f'Wise account error'
            msg = f'Wise returned {exec_res} status code for such account: {account_name}\n' \
                  f'Please review your account credentials or check wise account settings'
            mail_sender.send_mail(subj, default_email_to_send, msg)
            wise_state_manager.disable(access_token)


@app.get("/", response_class=HTMLResponse)
def get_all_account(request: Request):
    return templates.TemplateResponse("index.html",
                                      {"request": request,
                                       "disabled_accounts": wise_state_manager.disabled_accounts,
                                       "enabled_accounts": wise_state_manager.enabled_accounts})


@app.post("/")
def add_new_account(request: Request,
                    name: str = Form(),
                    access_token: str = Form(),
                    balance_currency: CurrencyType = Form(),
                    jar_currency: CurrencyType = Form()):
    try:
        new_account = WiseAccountManager(name, access_token, balance_currency,
                                         jar_currency)
    except InvalidAccessTokenError:
        flash(request, "Invalid api token", "The api token is invalid or there is no jar with such currency type or no balance with such currency type!")
        return templates.TemplateResponse("index.html",
                                          {"request": request,
                                           "disabled_accounts": wise_state_manager.disabled_accounts,
                                           "enabled_accounts": wise_state_manager.enabled_accounts})
    add_wise_account(new_account)
    wise_state_manager.add(new_account)
    return templates.TemplateResponse("index.html",
                                      {"request": request,
                                       "disabled_accounts": wise_state_manager.disabled_accounts,
                                       "enabled_accounts": wise_state_manager.enabled_accounts})


@app.get("/{access_token}/")
def change_account_status(access_token: str,
                          status: Literal['enable', 'disable'] = Query()):
    getattr(wise_state_manager, status)(access_token)
