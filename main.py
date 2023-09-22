import json
import platform
import sys
import aiohttp
import asyncio
from datetime import datetime, timedelta


DATE_FORMAT = "%d.%m.%Y"
TIME_FORMAT = "%H:%M"
DATETIME_FORMAT = f"{DATE_FORMAT} {TIME_FORMAT}"


async def get_exchange_rates_per_date(session, date):
    date = date.strftime(DATE_FORMAT)
    async with session.get(
        "https://api.privatbank.ua/p24api/exchange_rates?date=" + date
    ) as response:
        result = await response.json()
        return [date, result]


async def get_exchange_rates(n):
    datetime_now = datetime.now()
    async with aiohttp.ClientSession() as session:
        result = await asyncio.gather(
            *[
                get_exchange_rates_per_date(session, datetime_now - timedelta(days=i))
                for i in range(n)
            ]
        )
        return result


def handle_parameters(*args):
    if len(args) == 1:
        return (1,)
    try:
        n = int(args[1])
        offset = 2
    except ValueError:
        n = 1
        offset = 1
    if not 1 <= n <= 10:
        raise ValueError(
            "The first parameter to script can't be outside the range 1 - 10"
        )
    return n, *args[offset:]


def handle_data(data, currency_list):
    result = []
    for date, date_result in data:
        if date_result.get("status") == "error":
            date_info = {date: "Not found"}
        else:
            date_info = {}
            for currency_dict in date_result["exchangeRate"]:
                currency_label = currency_dict["currency"]
                if currency_label in currency_list:
                    sale_value = currency_dict.get("saleRate")
                    if not sale_value:
                        sale_value = currency_dict.get("saleRateNB")
                        sale_key = "saleNB"
                    else:
                        sale_key = "sale"
                    purchase_value = currency_dict.get("purchaseRate")
                    if not purchase_value:
                        purchase_value = currency_dict.get("purchaseRateNB")
                        purchase_key = "purchaseNB"
                    else:
                        purchase_key = "purchase"
                    date_info[currency_label] = {
                        sale_key: sale_value,
                        purchase_key: purchase_value,
                    }
            date_info = {date: date_info}
        result.append(date_info)
    return result


def json_view(data):
    return json.dumps(data, indent=4)


if __name__ == "__main__":
    try:
        n, *additional_currencies = handle_parameters(*sys.argv)
    except ValueError as error:
        print(f"ValueError: ", str(error))
        exit(-1)
    currency_list = ["EUR", "USD"]
    if additional_currencies:
        for currency in additional_currencies:
            currency_list.append(currency.upper())
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        data = asyncio.run(get_exchange_rates(n))
    except aiohttp.ClientConnectorError as error:
        print(f"Connection error: ", str(error))
        exit(-1)
    except aiohttp.client_exceptions.ContentTypeError:
        print(f"Content error: ", str(error))
        exit(-1)
    result = handle_data(data, currency_list)
    result = json_view(result)
    print(result)
