"""Реализация части запросов к MOEX ISS.

При необходимости могут быть дополнены:
    Полный перечень запросов https://iss.moex.com/iss/reference/
    Дополнительное описание https://fs.moex.com/files/6523
"""

import requests
from requests.auth import HTTPBasicAuth

from apimoex import client

__all__ = [
    "get_reference",
    "find_securities",
    "find_security_description",
    "get_market_candle_borders",
    "get_board_candle_borders",
    "get_market_candles",
    "get_board_candles",
    "get_board_dates",
    "get_board_securities",
    "get_market_history",
    "get_board_history",
    "get_index_tickers",
    "get_board_today_trades",
    "authenticate",
    "get_tradestats",
    "get_orderstats"
]


def _make_query(
    *,
    q: str | None = None,
    interval: int | None = None,
    start: str | None = None,
    end: str | None = None,
    date: str | None = None,
    table: str | None = None,
    columns: tuple[str, ...] | None = None,
) -> client.WebQuery:
    """Формирует дополнительные параметры запроса к MOEX ISS.

    В случае None значений не добавляются в запрос.

    :param q:
        Строка с частью характеристик бумаги для поиска.
    :param interval:
        Размер свечки.
    :param start:
        Начальная дата котировок.
    :param end:
        Конечная дата котировок.
    :param date:
        Точная дата (используется при получении тикеров в индексе).
    :param table:
        Таблица, которую нужно загрузить (для запросов, предполагающих наличие нескольких таблиц).
    :param columns:
        Кортеж столбцов, которые нужно загрузить.

    :return:
        Словарь с дополнительными параметрами запроса.
    """
    query: client.WebQuery = {}
    if q:
        query["q"] = q
    if interval:
        query["interval"] = interval
    if start:
        query["from"] = start
    if end:
        query["till"] = end
    if date:
        query["date"] = date
    if table:
        query["iss.only"] = f"{table},history.cursor"
    if columns:
        query[f"{table}.columns"] = ",".join(columns)

    return query


def _get_table(data: client.TablesDict, table: str) -> client.Table:
    """Извлекает конкретную таблицу из данных."""
    try:
        return data[table]
    except KeyError as err:
        raise client.ISSMoexError(f"Отсутствует таблица {table} в данных") from err


def _get_short_data(
    session: requests.Session,
    url: str,
    table: str,
    query: client.WebQuery | None = None,
) -> client.Table:
    """Получить данные для запроса с выдачей всей информации за раз.

    :param session:
        Сессия интернет соединения.
    :param url:
        URL запроса.
    :param table:
        Таблица, которую нужно выбрать.
    :param query:
        Дополнительные параметры запроса.

    :return:
        Конкретная таблица из запроса.
    """
    iss = client.ISSClient(session, url, query)
    data = iss.get()

    return _get_table(data, table)


def _get_long_data(
    session: requests.Session,
    url: str,
    table: str,
    query: client.WebQuery | None = None,
) -> client.Table:
    """Получить данные для запроса, в котором информация выдается несколькими блоками.

    :param session:
        Сессия интернет соединения.
    :param url:
        URL запроса.
    :param table:
        Таблица, которую нужно выбрать.
    :param query:
        Дополнительные параметры запроса.

    :return:
        Конкретная таблица из запроса.
    """
    iss = client.ISSClient(session, url, query)
    data = iss.get_all()

    return _get_table(data, table)


def get_reference(session: requests.Session, placeholder: str = "boards") -> list[dict[str, str | int | float]]:
    """Получить перечень доступных значений плейсхолдера в адресе запроса.

    Например в описание запроса https://iss.moex.com/iss/reference/32 присутствует следующий адрес
    /iss/engines/[engine]/markets/[market]/boards/[board]/securities с плейсхолдерами engines, markets и boards.

    Описание запроса - https://iss.moex.com/iss/reference/28

    :param session:
        Сессия интернет соединения.
    :param placeholder:
        Наименование плейсхолдера в адресе запроса: engines, markets, boards, boardgroups, durations, securitytypes,
        securitygroups, securitycollections

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = "https://iss.moex.com/iss/index.json"

    return _get_short_data(session, url, placeholder)


def find_securities(
    session: requests.Session,
    string: str,
    columns: tuple[str, ...] | None = ("secid", "regnumber"),
) -> client.Table:
    """Найти инструменты по части Кода, Названию, ISIN, Идентификатору Эмитента, Номеру гос.регистрации.

    Один из вариантов использования - по регистрационному номеру узнать предыдущие тикеры эмитента, и с помощью
    нескольких запросов об истории котировок собрать длинную историю с использованием всех предыдущих тикеров.

    Описание запроса - https://iss.moex.com/iss/reference/5

    :param session:
        Сессия интернет соединения.
    :param string:
        Часть Кода, Названия, ISIN, Идентификатора Эмитента, Номера гос.регистрации.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию тикер и номер государственно регистрации.
        Если пустой или None, то загружаются все столбцы.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = "https://iss.moex.com/iss/securities.json"
    table = "securities"
    query = _make_query(q=string, table=table, columns=columns)

    return _get_short_data(session, url, table, query)


def find_security_description(
    session: requests.Session,
    security: str,
    columns: tuple[str, ...] | None = ("name", "title", "value"),
) -> client.Table:
    """Получить спецификацию инструмента.

    Один из вариантов использования - по тикеру узнать дату начала торгов.

    Описание запроса - https://iss.moex.com/iss/reference/13

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию краткое название, длинное название на русском и значение
        показателя.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = f"https://iss.moex.com/iss/securities/{security}.json"
    table = "description"
    query = _make_query(table=table, columns=columns)

    return _get_short_data(session, url, table, query)


def get_market_candle_borders(
    session: requests.Session,
    security: str,
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить таблицу интервалов доступных дат для свечей различного размера на рынке для всех режимов торгов.

    Описание запроса - https://iss.moex.com/iss/reference/156

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/securities/{security}/candleborders.json"
    table = "borders"

    return _get_short_data(session, url, table)


def get_board_candle_borders(
    session: requests.Session,
    security: str,
    board: str = "TQBR",
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить таблицу интервалов доступных дат для свечей различного размера в указанном режиме торгов.

    Описание запроса - https://iss.moex.com/iss/reference/48

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param board:
        Режим торгов - по умолчанию основной режим торгов T+2.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = (
        f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/"
        f"boards/{board}/securities/{security}/candleborders.json"
    )
    table = "borders"

    return _get_short_data(session, url, table)


def get_market_candles(
    session: requests.Session,
    security: str,
    interval: int = 24,
    start: str | None = None,
    end: str | None = None,
    columns: tuple[str, ...] | None = (
        "begin",
        "open",
        "close",
        "high",
        "low",
        "value",
        "volume",
    ),
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить свечи в формате HLOCV указанного инструмента на рынке для основного режима торгов за интервал дат.

    Если торговля идет в нескольких основных режимах, то на один интервал времени может быть выдано несколько свечек -
    по свечке на каждый режим. Предположительно такая ситуация может произойти для свечек длиннее 1 дня в периоды, когда
    менялся режим торгов.

    Описание запроса - https://iss.moex.com/iss/reference/155

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param interval:
        Размер свечки - целое число 1 (1 минута), 10 (10 минут), 60 (1 час), 24 (1 день), 7 (1 неделя), 31 (1 месяц) или
        4 (1 квартал). По умолчанию дневные данные.
    :param start:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены с начала истории.
    :param end:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены до конца истории. Для текущего дня будут
        загружены не окончательные данные, если торги продолжаются.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию момент начала свечки и HLOCV. Если пустой или None, то
        загружаются все столбцы.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/securities/{security}/candles.json"
    table = "candles"
    query = _make_query(interval=interval, start=start, end=end, table=table, columns=columns)

    return _get_long_data(session, url, table, query)


def get_board_candles(
    session: requests.Session,
    security: str,
    interval: int = 24,
    start: str | None = None,
    end: str | None = None,
    columns: tuple[str, ...] | None = (
        "begin",
        "open",
        "close",
        "high",
        "low",
        "value",
        "volume",
    ),
    board: str = "TQBR",
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить свечи в формате HLOCV указанного инструмента в указанном режиме торгов за интервал дат.

    Описание запроса - https://iss.moex.com/iss/reference/46

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param interval:
        Размер свечки - целое число 1 (1 минута), 10 (10 минут), 60 (1 час), 24 (1 день), 7 (1 неделя), 31 (1 месяц) или
        4 (1 квартал). По умолчанию дневные данные.
    :param start:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены с начала истории.
    :param end:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены до конца истории. Для текущего дня будут
        загружены не окончательные данные, если торги продолжаются.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию момент начала свечки и HLOCV. Если пустой или None, то
        загружаются все столбцы.
    :param board:
        Режим торгов - по умолчанию основной режим торгов T+2.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = (
        f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/"
        f"boards/{board}/securities/{security}/candles.json"
    )
    table = "candles"
    query = _make_query(interval=interval, start=start, end=end, table=table, columns=columns)

    return _get_long_data(session, url, table, query)


def get_board_dates(
    session: requests.Session,
    board: str = "TQBR",
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить интервал дат, доступных в истории для рынка по заданному режиму торгов.

    Описание запроса - https://iss.moex.com/iss/reference/26

    :param session:
        Сессия интернет соединения.
    :param board:
        Режим торгов - по умолчанию основной режим торгов T+2.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список из одного элемента - словаря с ключами 'from' и 'till'.
    """
    url = f"https://iss.moex.com/iss/history/engines/{engine}/markets/{market}/boards/{board}/dates.json"
    table = "dates"

    return _get_short_data(session, url, table)


def get_board_securities(
    session: requests.Session,
    table: str = "securities",
    columns: tuple[str, ...] | None = ("SECID", "REGNUMBER", "LOTSIZE", "SHORTNAME"),
    board: str = "TQBR",
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить таблицу инструментов по режиму торгов со вспомогательной информацией.

    Описание запроса - https://iss.moex.com/iss/reference/32

    :param session:
        Сессия интернет соединения.
    :param table:
        Таблица с данными, которую нужно вернуть: securities - справочник торгуемых ценных бумаг, marketdata -
        данные с результатами торгов текущего дня.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию тикер, номер государственно регистрации,
        размер лота и краткое название. Если пустой или None, то загружаются все столбцы.
    :param board:
        Режим торгов - по умолчанию основной режим торгов T+2.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/boards/{board}/securities.json"
    query = _make_query(table=table, columns=columns)

    return _get_short_data(session, url, table, query)


def get_market_history(
    session: requests.Session,
    security: str,
    start: str | None = None,
    end: str | None = None,
    columns: tuple[str, ...] | None = (
        "BOARDID",
        "TRADEDATE",
        "CLOSE",
        "VOLUME",
        "VALUE",
    ),
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить историю по одной бумаге на рынке для всех режимов торгов за интервал дат.

    На одну дату может приходиться несколько значений, если торги шли в нескольких режимах.

    Описание запроса - https://iss.moex.com/iss/reference/63

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param start:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены с начала истории.
    :param end:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены до конца истории.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию режим торгов, дата торгов, цена закрытия и объем в
        штуках и стоимости. Если пустой или None, то загружаются все столбцы.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = f"https://iss.moex.com/iss/history/engines/{engine}/markets/{market}/securities/{security}.json"
    table = "history"
    query = _make_query(start=start, end=end, table=table, columns=columns)

    return _get_long_data(session, url, table, query)


def get_board_history(
    session: requests.Session,
    security: str,
    start: str | None = None,
    end: str | None = None,
    columns: tuple[str, ...] | None = (
        "BOARDID",
        "TRADEDATE",
        "CLOSE",
        "VOLUME",
        "VALUE",
    ),
    board: str = "TQBR",
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить историю торгов для указанной бумаги в указанном режиме торгов за указанный интервал дат.

    Описание запроса - https://iss.moex.com/iss/reference/65

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param start:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены с начала истории.
    :param end:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены до конца истории.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию режим торгов, дата торгов, цена закрытия и объем в
        штуках и стоимости. Если пустой или None, то загружаются все столбцы.
    :param board:
        Режим торгов - по умолчанию основной режим торгов T+2.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = (
        f"https://iss.moex.com/iss/history/engines/{engine}/markets/{market}/"
        f"boards/{board}/securities/{security}.json"
    )
    table = "history"
    query = _make_query(start=start, end=end, table=table, columns=columns)

    return _get_long_data(session, url, table, query)


def get_index_tickers(
    session: requests.Session,
    index: str,
    date: str | None = None,
    columns: tuple[str, ...] | None = (
        "ticker",
        "from",
        "till",
        "tradingsession",
    ),
    market: str = "index",
    engine: str = "stock",
) -> client.Table:
    """Получить информацию по составу указанного индекса за указанную дату.

    Описание запроса - https://iss.moex.com/iss/reference/148

    Список индексов - https://iss.moex.com/iss/statistics/engines/stock/markets/index/analytics

    :param session:
        Сессия интернет соединения.
    :param index:
        Название индекса. Например, IMOEX.
    :param date:
        Дата вида ГГГГ-ММ-ДД. Если указано, то будут показаны только активные инструменты,
        по которым тогда рассчитывалось значение индекса. Если в указанный день не было торгов, то вернёт пустой список!
        При отсутствии данные будут загружены с начала истории.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию режим торгов, дата торгов, цена закрытия и объем в
        штуках и стоимости. Если пустой или None, то загружаются все столбцы.
    :param market:
        Рынок - по умолчанию индексы.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = f"https://iss.moex.com/iss/statistics/engines/{engine}/markets/{market}/" f"analytics/{index}/tickers.json"
    table = "tickers"
    query = _make_query(date=date, table=table, columns=columns)

    return _get_short_data(session, url, table, query)


def get_board_today_trades(
    session: requests.Session,
    security: str,
    tradeno: str = '',
    columns: tuple[str, ...] | None = (
            "TRADENO",
            "TRADETIME",
            "BOARDID",
            "SECID",
            "PRICE",
            "QUANTITY",
            "VALUE",
            "PERIOD",
            "TRADETIME_GRP",
            "SYSTIME",
            "BUYSELL",
            "DECIMALS",
            "TRADINGSESSION"),
    board: str = "TQBR",
    market: str = "shares",
    engine: str = "stock",
) -> client.Table:
    """Получить сделки указанного инструмента в указанном режиме торгов за сегодня.

    Описание запроса - https://iss.moex.com/iss/reference/55

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию момент начала свечки и HLOCV. Если пустой или None, то
        загружаются все столбцы.
    :param board:
        Режим торгов - по умолчанию основной режим торгов T+2.
    :param market:
        Рынок - по умолчанию акции.
    :param engine:
        Движок - по умолчанию акции.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = (
        f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/"
        f"boards/{board}/securities/{security}/trades.json"
    )
    table = "trades"
    query = _make_query(table=table, columns=columns, )
    if len(tradeno)>0:
        query['tradeno'] = tradeno

    return _get_long_data(session, url, table, query)


def authenticate(session: requests.Session, username: str, password: str) -> bool:
    
    """Для аутентификации пользователей используется basic-аутентификация. и передаются серверу в заголовке запроса на https://passport.moex.com/authenticate
    При успешной аутентификации сервер возвращает cookie c именем MicexPassportCert. Далее этот токен должен передаваться при последующих запросах.
    
    Описание запроса - https://moexalgo.github.io/api/rest/

    :param session:
        Сессия интернет соединения.
    :param username:
        iss moex username 
    :param password:
        iss moex password

    :return:
        True в случае успешной авторизации
    """
    url = "https://passport.moex.com/authenticate"
    r = False

    with session.get(url, auth = HTTPBasicAuth(username, password)) as respond:
        r = respond.status_code == 200
        
    return r


def get_tradestats(
    session: requests.Session,
    security: str,
    start: str | None = None,
    end: str | None = None,
    columns: tuple[str, ...] | None = (
            "tradedate",
            "tradetime",
            "secid",
            "pr_open",
            "pr_high",
            "pr_low",
            "pr_close",
            "pr_std",
            "vol",
            "val",
            "trades",
            "pr_vwap",
            "pr_change",
            "trades_b",
            "trades_s",
            "val_b",
            "val_s",
            "vol_b",
            "vol_s",
            "disb",
            "pr_vwap_b",
            "pr_vwap_s",
            "SYSTIME",
            "sec_pr_open",
            "sec_pr_high",
            "sec_pr_low",
            "sec_pr_close"),
) -> client.Table:
    """Метрики рассчитанные на основе потока сделок (tradestats). Требуется авторизация ISS MOEX

    Описание запроса - https://moexalgo.github.io/api/rest/

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию момент начала свечки и HLOCV. Если пустой или None, то
        загружаются все столбцы.
    :param start:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены с начала истории.
    :param end:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены до конца истории.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = (
        f"https://iss.moex.com/iss/datashop/algopack/eq/tradestats/{security}.json"
    )
    table = "data"
    query = _make_query(start=start, end=end, table=table, columns=columns)

    return _get_long_data(session, url, table, query)

def get_orderstats(
    session: requests.Session,
    security: str,
    start: str | None = None,
    end: str | None = None,
    columns: tuple[str, ...] | None = (
            "tradedate",
            "tradetime",
            "secid",
            "put_orders_b",
            "put_orders_s",
            "put_val_b",
            "put_val_s",
            "put_vol_b",
            "put_vol_s",
            "put_vwap_b",
            "put_vwap_s",
            "put_vol",
            "put_val",
            "put_orders",
            "cancel_orders_b",
            "cancel_orders_s",
            "cancel_val_b",
            "cancel_val_s",
            "cancel_vol_b",
            "cancel_vol_s",
            "cancel_vwap_b",
            "cancel_vwap_s",
            "cancel_vol",
            "cancel_val",
            "cancel_orders",
            "SYSTIME"),
) -> client.Table:
    """Метрики рассчитанные на основе потока заявок (orderstats). Требуется авторизация ISS MOEX

    Описание запроса - https://moexalgo.github.io/api/rest/

    :param session:
        Сессия интернет соединения.
    :param security:
        Тикер ценной бумаги.
    :param columns:
        Кортеж столбцов, которые нужно загрузить - по умолчанию момент начала свечки и HLOCV. Если пустой или None, то
        загружаются все столбцы.
    :param start:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены с начала истории.
    :param end:
        Дата вида ГГГГ-ММ-ДД. При отсутствии данные будут загружены до конца истории.

    :return:
        Список словарей, которые напрямую конвертируется в pandas.DataFrame.
    """
    url = (
        f"https://iss.moex.com/iss/datashop/algopack/eq/orderstats/{security}.json"
    )
    table = "data"
    query = _make_query(start=start, end=end, table=table, columns=columns)

    return _get_long_data(session, url, table, query)
