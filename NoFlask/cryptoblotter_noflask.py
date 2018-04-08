import cryptocompare
import datetime
import re
import time
import pandas as pd
import requests
from math import sqrt
import pymongo
from pymongo import MongoClient
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def start_up ():
    loop = 1
    print("Hello, here is your blotter for the day!")
    cryptos = {"ETH": "Ethereum",
              "XMR": "Monero",
              "ZEC": 'ZCash',
              "BTC": 'Litecoin',
              "NEO": 'NEO'}
    blotter = generate_dataframe(cryptos)
    print(blotter)
    transaction_question = "What would you like to do? A) Trade B) Update Blotter C) Exit Program"
    while loop == 1:
        transaction_values = transactions(transaction_question, cryptos, blotter)
        if transaction_values['transaction'] == "C":
            loop = 2

def set_up_mongodb():
    MONGODB_URI = "mongodb://test:test@ds129043.mlab.com:29043/cryptocurrency_blotter"
    client = MongoClient(MONGODB_URI, connectTimeoutMS = 30000)
    db = client.get_database("cryptocurrency_blotter")
    user_records = db.user_records
    return user_records

def push_record(record):
    user_records = set_up_mongodb()
    user_records.insert_one(record)

def push_blotter_data(blotter):
    blotter_dict = blotter.to_dict('index')
    push_record(blotter_dict)

def generate_dataframe(cryptos): 
    # setup dataframe
    cols = ['Ticker','Position', 'Market', 'WAP', 'UPL', 'RPL', 'Cash', "P/L", "% Shares", "% Dollars"]
    blotter = pd.DataFrame(columns = cols)
    pd.set_option('display.float_format', lambda x: '%.3f' % x)

    # loop through function get_price
    for crypto in cryptos.keys():
        Ticker = crypto
        Position = 0
        Market = get_price(crypto)
        WAP = 0
        UPL = 0
        RPL = 0
        Cash = 0
        PL = 0
        Shares = 0
        Dollars = 0 
        temp_blotter = pd.Series([Ticker, Position, as_currency(Market), WAP,  UPL, RPL, Cash, PL, Shares, Dollars])
        df_blotter = pd.DataFrame([list(temp_blotter)], columns = cols)
        blotter = blotter.append(df_blotter)

    cash = pd.Series(["Cash", as_currency(10000000), as_currency(10000000), " ",  " ", " ", " ", " ", " ", " "])
    cash_df = pd.DataFrame([list(cash)], columns = cols)
    blotter = blotter.append(cash_df)   
    blotter = blotter.set_index('Ticker')
    return blotter

def get_price(crypto):
    dict_price = cryptocompare.get_price(crypto)
    string_price = str(dict_price)
    regex_price = re.findall('\d+[\,\.]{1}\d{1,2}', string_price)
    if (regex_price == []):
        new_regex_price = re.findall('\d+', str(string_price))
        price = float(new_regex_price[0])
    else:
        price = float(regex_price[0])
    return(price)

def as_float(number):
    number = str(number)
    if number != 0 and ',' in number:
        number = number.replace(",","")
        number = float(number.replace("$",""))
    elif number != 0:
        number = float(number.replace("$",""))
    return number

def calculate_new_variables(position, WAP, UPL, RPL, blotter):
    cash_position = blotter.loc["Cash", "Position"]
    total_cash = as_float(cash_position)
    stocks_purchased = blotter['Position'].head(5).sum()
    if WAP == []:
        Cash = " "
    else:
        Cash = position * WAP
    if UPL == []:
        PL = " "
    else:
        PL = UPL + RPL
    if stocks_purchased == 0:
        Shares = 0
    else:
        Shares =  round(position/stocks_purchased, 2)
    if cash_position == 0 or Cash == 0:
        Percent_Dollars = 0
    else:
        Percent_Dollars = Cash/total_cash
    Cash = as_currency(Cash)
    PL = as_currency(PL)
    Shares = str(Shares) + "%"
    Percent_Dollars = str(round(Percent_Dollars, 2)) + "%"
    return {"Cash": Cash, "PL": PL, "Shares": Shares, "Percent_Dollars": Percent_Dollars}

def update_dataframe (cryptos, blotter):
    cols = ['Ticker','Position', 'Market', 'WAP', 'UPL', 'RPL', 'Cash', "P/L", "% Shares", "% Dollars"]
    crypto_data = pd.DataFrame(columns = cols)

    #update crypto data
    for crypto in cryptos.keys():
        Ticker = crypto
        Position = blotter.loc[crypto, "Position"]
        Market = get_price(crypto)
        WAP = as_float(clean_data(blotter, crypto, "WAP"))
        # update UPL
        current_UPL = clean_data(blotter, crypto, "UPL")
        current_market = clean_data(blotter, crypto, "Market")
        if Market != current_market:
            UPL = as_float((Market - WAP) * Position)
        else:
            UPL = as_float(current_UPL)
        # obtain RPL
        RPL = as_float(blotter.loc[crypto, "RPL"])
        # new variables added
        variables = calculate_new_variables(Position, WAP, UPL, RPL, blotter)
        temp_blotter = pd.Series([Ticker, Position, as_currency(Market), as_currency(WAP),  as_currency(UPL), as_currency(RPL), variables['Cash'], variables['PL'], variables['Shares'], variables['Percent_Dollars']])
        df_blotter = pd.DataFrame([list(temp_blotter)], columns = cols)
        crypto_data = crypto_data.append(df_blotter)

    #update cash data
    cash_position = blotter.loc["Cash", "Position"]
    cash_market = blotter.loc["Cash", "Market"]
    cash = pd.Series(["Cash", cash_position, cash_market, " ",  " ", " ", " ", " ", " ", " "])
    cash_df = pd.DataFrame([list(cash)], columns = cols)
    crypto_data = crypto_data.append(cash_df)   
    crypto_data = crypto_data.set_index('Ticker')
    #update blotter
    blotter.update(crypto_data)
    print(blotter)
    return (blotter)

def clean_data (blotter, index, column):
    value = str(blotter.loc[index, column])
    if value != 0:
        value = value.replace(",","")
        value = float(value.replace("$",""))
    return(value)

def as_currency(amount):
    if type(amount) == str:
        return '${:,.2f}'.format(amount)
    elif amount >= -10000000:
        return '${:,.2f}'.format(amount)

def transactions(transaction_question, cryptos, blotter):
    transaction = input(transaction_question).upper()
    if transaction == "A":
        blotter = get_transactions(cryptos, blotter)
        push_blotter_data(blotter)
    elif transaction == "B":
        blotter = update_dataframe(cryptos, blotter)
        push_blotter_data(blotter)
    elif transaction == "C":
        print("Goodbye")
    else:
        print("Error choose an appropriate action")
    return {"transaction": transaction, "blotter": blotter}

def daily_price_historical(symbol, comparison_symbol, all_data=True, limit=100, aggregate=1, exchange=''):
    # https://medium.com/@galea/cryptocompare-api-quick-start-guide-ca4430a484d4
    url = 'https://min-api.cryptocompare.com/data/histoday?fsym={}&tsym={}&limit={}&aggregate={}'\
            .format(symbol.upper(), comparison_symbol.upper(), limit, aggregate)
    if exchange:
        url += '&e={}'.format(exchange)
    if all_data:
        url += '&allData=true'
    page = requests.get(url)
    data = page.json()['Data']
    df = pd.DataFrame(data)
    df['timestamp'] = [datetime.datetime.fromtimestamp(d) for d in df.time]
    df = df.set_index("timestamp")
    historic_data = df.tail(120)
    return historic_data

def historic_price_chart(df, crypto):
    short_rolling_df = df.rolling(window=20).mean()

    fig = plt.figure(figsize=(15,9))
    ax = fig.add_subplot(1,1,1)
    plt.title(crypto)
    historic_data = df.tail(100)
    short_rolling_data = short_rolling_df.tail(100)
    Price = historic_data[['close']]
    Date = historic_data.index.values
    ax.plot(Date, Price, label = "Closing Price")
    short_rolling = short_rolling_data[['close']]
    ax.plot(Date, short_rolling, label = '20 Day Simple Moving Average')

    ax.legend(loc='best')
    ax.set_ylabel('Price in $ (' + crypto + ")")
    plt.show()
    fig.savefig('historic.png')

def avg_price(symbol, comparison_symbol, UTCHourDiff=-24, exchange=''):
    url = 'https://min-api.cryptocompare.com/data/dayAvg?fsym={}&tsym={}&UTCHourDiff={}'\
            .format(symbol.upper(), comparison_symbol.upper(), UTCHourDiff)
    if exchange:
        url += '&e={}'.format(exchange)
    page = requests.get(url)
    data = page.json()
    regex_price = re.findall('\d+[\,\.]{1}\d{1,2}', str(data))
    if (regex_price == []):
        new_regex_price = re.findall('\d+', str(val))
        price = float(new_regex_price[0])
    else:
        price = float(regex_price[0])
    return price

def price_24_hours(symbol, comparison_symbol, exchange=''):
    url = 'https://min-api.cryptocompare.com/data/histominute?fsym={}&tsym={}&limit=10000&aggregate=3&e=CCCAGG'\
            .format(symbol.upper(), comparison_symbol.upper())
    if exchange:
        url += '&e={}'.format(exchange)
    page = requests.get(url)
    data = page.json()['Data']
    df = pd.DataFrame(data)
    df['timestamp'] = [datetime.datetime.fromtimestamp(d) for d in df.time]
    df = df.set_index("timestamp")
    return df

def crypto_analytics(df, crypto):
    price = df['close'].values
    min_val = min(price)
    max_val = max(price)
    num_items = len(price)
    mean = sum(price) / num_items
    differences = [x - mean for x in price]
    sq_differences = [d ** 2 for d in differences]
    ssd = sum(sq_differences)
    variance = ssd / num_items
    sd = round(sqrt(variance), 2)
    avg_price_crypto = avg_price(crypto, "USD")
    d = {"cryptocurrency": [crypto], "min": [min_val], "max": [max_val], "sd": [sd], "avg price": [avg_price_crypto]}
    stats = pd.DataFrame(data = d).set_index('cryptocurrency')
    return stats

def show_plots_and_stats(crypto):
    historic_data = daily_price_historical(crypto, "USD")
    historic_price_chart(historic_data, crypto)
    data_24_hours = price_24_hours(crypto, "USD")
    stats = crypto_analytics(data_24_hours, crypto)
    return (stats)

def purchase (crypto, price, shares_for_purchase, blotter):
    # generating values for the dataframe
    cols = ['Ticker','Position', 'Market', 'WAP', 'UPL', 'RPL', 'Cash', "P/L", "% Shares", "% Dollars"]
    Ticker = crypto
    current_shares = blotter.loc[crypto, "Position"]
    Position = current_shares + shares_for_purchase
    purchase_price = float(price)

    # calcauting WAP values
    current_WAP = clean_data(blotter, crypto, "WAP")
    if current_shares == 0:
        WAP = purchase_price
    else:
        WAP = (((current_WAP * current_shares)/current_shares) + ((shares_for_purchase * purchase_price)/shares_for_purchase))/2

    # determining if value of crypto has changed since getting price for UPL
    Values = get_price(crypto)
    Market = float(Values)
    UPL = (Market - WAP) * Position

    # get cash position, cash market values, and current RPL values
    current_cash = clean_data(blotter, "Cash", "Position")
    current_market = clean_data(blotter, "Cash", "Market")
    RPL = blotter.loc[crypto, "RPL"]
    Cash_Position = current_cash - (shares_for_purchase * purchase_price)
    Cash_Market = Cash_Position

    # update blotter crypto info
    # new variables added
    WAP = as_float(WAP)
    UPL = as_float(UPL)
    RPL = as_float(RPL)
    variables = calculate_new_variables(Position, WAP, UPL, RPL, blotter)
    updated_info = pd.Series([Ticker, Position, as_currency(Market), as_currency(WAP),  as_currency(UPL), as_currency(RPL), variables['Cash'], variables['PL'], variables['Shares'], variables['Percent_Dollars']])
    crypto_df = pd.DataFrame([list(updated_info)], columns = cols)
    crypto_df = crypto_df.set_index('Ticker')
    # update blotter cash info
    updated_cash_info = pd.Series(["Cash", as_currency(Cash_Position), as_currency(Cash_Market), "",  "", "", " ", " ", " ", " "])
    cash_df = pd.DataFrame([list(updated_cash_info)], columns = cols)
    cash_df = cash_df.set_index("Ticker")
    # blotter.update()
    blotter.update(crypto_df)
    blotter.update(cash_df)
    return (blotter)

def sell (crypto, price, shares_for_selling, blotter):
    # generating values for the dataframe
    cols = ['Ticker','Position', 'Market', 'WAP', 'UPL', 'RPL', 'Cash', "P/L", "% Shares", "% Dollars"]
    Ticker = crypto
    current_shares = blotter.loc[crypto, "Position"]
    Position = current_shares - shares_for_selling
    selling_price = float(price)
    Market = clean_data(blotter, crypto, "Market")

    # calcauting WAP values
    current_WAP = clean_data(blotter, crypto, "WAP")
    if Position == 0:
        WAP = 0
    else:
        WAP = (((current_WAP * Position)/Position) + ((shares_for_selling * selling_price)/shares_for_selling))/2

    # UPL changes to cryptos currently have
    UPL = (Position * (Market - WAP))
    # RPL gets recoginized
    RPL = ((price - current_WAP) * shares_for_selling)
    # new Market becomes last transaction price
    Market = price

    # get cash position, cash market values, and current RPL values
    current_cash = clean_data(blotter, "Cash", "Position")
    Cash_Position = current_cash + RPL + (price * shares_for_selling)
    Cash_Market = Cash_Position

    #update blotter crypto info
    WAP = as_float(WAP)
    UPL = as_float(UPL)
    RPL = as_float(RPL)
    variables = calculate_new_variables(Position, WAP, UPL, RPL, blotter)
    updated_info = pd.Series([Ticker, Position, as_currency(Market), as_currency(WAP),  UPL, as_currency(RPL), variables['Cash'], variables['PL'], variables['Shares'], variables['Percent_Dollars']])
    crypto_df = pd.DataFrame([list(updated_info)], columns = cols)
    crypto_df = crypto_df.set_index('Ticker')
    # update blotter cash info
    updated_cash_info = pd.Series(["Cash", as_currency(Cash_Position), as_currency(Cash_Market), "",  "", "", " ", " ", " ", " "])
    cash_df = pd.DataFrame([list(updated_cash_info)], columns = cols)
    cash_df = cash_df.set_index("Ticker")
    #blotter.update()
    blotter.update(crypto_df)
    blotter.update(cash_df)
    return (blotter)

def get_crypto(cryptos):
    loop = 1
    print("What crypto would you like to trade? As a reminder, below are the cryptos available.")
    print(cryptos.keys())
    crypto = input("Enter crypto:").upper()
    if crypto in cryptos.keys():
        loop = 2
    while loop == 1:
        print("Error. Choose one of the above five cryptos")
        crypto = input("What crypto would you like to trade?").upper()
        if crypto in cryptos.keys():
            loop = 2
    return (crypto)

def get_transactions(cryptos, blotter):
    crypto = get_crypto(cryptos)
    buy_sell = input("Would you like to buy or sell?")
    if buy_sell == "buy":
        Values = get_price(crypto)
        df = show_plots_and_stats(crypto)
        print(df)
        price_question = "The price is " + str(Values) + ". Historical data and relevant stats are shown here. Continue? Write yes or no."
        price_ok = input(price_question).lower()
        if price_ok == "yes":
            shares = float(input("How many shares would you like to purchase?"))
            if shares <0:
                print("Error. Cannot purchase a negative number")
            else:
                current_cash = clean_data(blotter, "Cash", "Position")
                total_purchase = float(Values) * float(shares)
                if total_purchase > current_cash:
                    print("Error. Do not have adequate funds to complete this transaction")
                else:
                    blotter = purchase(crypto, float(Values), float(shares), blotter)
                    print("Thank you, your blotter is updating")
                    print(blotter)
    if buy_sell == "sell":
        Values = get_price(crypto)
        df = show_plots_and_stats(crypto)
        print(df)
        price_question = "The selling price is " + str(Values) + ". Historical data and relevant stats are shown here. Continue? Write yes or no."
        price_ok = input(price_question).lower()
        if price_ok == "yes":
            current_cryptos = clean_data(blotter, crypto, "Position")
            selling_question = "You currently have " + str(current_cryptos) + " shares of " + str(crypto) + ". How many shares would you like to sell?"
            shares = float(input(selling_question))
            if shares <0:
                print("Error. Cannot purchase a negative number")
            else:
                if current_cryptos < shares:
                    print("Error. Selling more cryptos than you own.")
                else:
                    blotter = sell(crypto, float(Values), float(shares), blotter)
                    print("Thank you, your blotter is updating")
                    print(blotter)
    return(blotter)

if __name__ == '__main__':
    start_up()
    set_up_mongodb()