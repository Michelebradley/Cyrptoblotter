import cryptocompare
import datetime
import re
import time
import matplotlib.pyplot as plt
import pandas as pd
import requests
from math import sqrt
import pymongo
from pymongo import MongoClient
from io import BytesIO
from flask import Flask, session, render_template, request, send_file, make_response, url_for
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure


app = Flask(__name__)
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

@app.route("/")
def template():
	cryptos = {"ETH": "Ethereum",
              "XMR": "Monero",
              "ZEC": 'ZCash',
              "BTC": 'Litecoin',
              "NEO": 'NEO'}
	options = pd.DataFrame.from_dict(cryptos, orient = "index").rename(columns={0:'Cryptos'})
	blotter = generate_dataframe(cryptos)
	session['blotter'] = blotter.to_json()
	return render_template('index.html', vars = [blotter, cryptos], tables = [options.to_html(), blotter.to_html()])
#https://sarahleejane.github.io/learning/python/2015/08/09/simple-tables-in-webapps-using-flask-and-pandas-with-python.html
#https://pythonspot.com/flask-web-app-with-python/
#https://stackoverflow.com/questions/27611216/how-to-pass-a-variable-between-flask-pages

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

@app.route("/numshares", methods = ['POST'])
def get_crypto_name():
    crypto = '{}'.format(request.form['cryptocurrency']) 
    blotter_json = pd.read_json(session['blotter'])
    blotter = pd.DataFrame(blotter_json)
    crypto_chosen = str(crypto)
    session['crypto_value'] = crypto_chosen
    data_24_hours = price_24_hours(crypto_chosen, "USD")
    stats = crypto_analytics(data_24_hours, crypto_chosen)
    return render_template('stats.html', var = [crypto, blotter], tables = [stats.to_html(), blotter.to_html()])

@app.route("/startup", methods = ['POST'])
def get_shares_sell():
    crypto_chosen = session['crypto_value']
    blotter_json = pd.read_json(session['blotter'])
    blotter = pd.DataFrame(blotter_json)
    data_24_hours = price_24_hours(crypto_chosen, "USD")
    stats = crypto_analytics(data_24_hours, crypto_chosen)
    buy_sell_val = request.form['buy_sell']
    session['buy_sell_val'] = buy_sell_val
    return render_template('numshares.html', var = [crypto_chosen, blotter], tables = [stats.to_html(), blotter.to_html()])

# updating blotter info

@app.route("/updated", methods = ['POST'])
def update():
    crypto = session['crypto_value']
    blotter_json = pd.read_json(session['blotter'])
    blotter = pd.DataFrame(blotter_json)
    buy_sell_val = session['buy_sell_val']
    amount = request.form['amount']
    Values = get_price(crypto)
    if buy_sell_val == 'buy':
    	blotter = purchase(crypto, Values, amount, blotter)
    else:
    	blotter = sell(crypto, Values, amount, blotter)
    session['blotter'] = blotter.to_json()
    push_blotter_data(blotter)
    return render_template('updated.html', vars= [crypto, buy_sell_val, amount, blotter], tables = [blotter.to_html()])

# stat and plot info 
@app.route('/plot.png')
def plot():
    crypto_chosen = session['crypto_value']
    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)

    df = daily_price_historical(crypto_chosen, "USD")
    short_rolling_df = df.rolling(window=20).mean()
    historic_data = df.tail(100)
    short_rolling_data = short_rolling_df.tail(100)
    Price = historic_data[['close']]
    Date = historic_data.index.values

    fig.suptitle(crypto_chosen)
    axis.plot(Date, Price, label = "Closing Price")
    short_rolling = short_rolling_data[['close']]
    axis.plot(Date, short_rolling, label = "20 Day Simple Moving Average")
    
    fig.autofmt_xdate()
    axis.legend(loc='best')
    axis.set_ylabel('Price in $')

    canvas = FigureCanvas(fig)
    output = BytesIO()
    canvas.print_png(output)
    response = make_response(output.getvalue())
    response.mimetype = 'image/png'
    return response

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

def purchase (crypto, price, shares_for_purchase, blotter):
    # generating values for the dataframe
    cols = ['Ticker','Position', 'Market', 'WAP', 'UPL', 'RPL', 'Cash', "P/L", "% Shares", "% Dollars"]
    Ticker = crypto
    current_shares = blotter.loc[crypto, "Position"]
    shares_for_purchase = int(shares_for_purchase)
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

def calculate_new_variables(position, WAP, UPL, RPL, blotter):
    cash_position = blotter.loc["Cash", "Position"]
    total_cash = as_float(cash_position)
    temp_blotter = blotter[blotter.index != "Cash"]
    stocks_purchased = temp_blotter['Position'].head(5).sum()
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

def sell (crypto, price, shares_for_selling, blotter):
    # generating values for the dataframe
    cols = ['Ticker','Position', 'Market', 'WAP', 'UPL', 'RPL', 'Cash', "P/L", "% Shares", "% Dollars"]
    Ticker = crypto
    current_shares = blotter.loc[crypto, "Position"]
    shares_for_selling = int(shares_for_selling)
    Position = current_shares - shares_for_selling
    import sys
    print(current_shares, file=sys.stdout)
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
    print(current_cash, file=sys.stdout)
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

# cleaning functions 

def as_float(number):
    number = str(number)
    if number != 0 and ',' in number:
        number = number.replace(",","")
        number = float(number.replace("$",""))
    elif number != 0:
        number = float(number.replace("$",""))
    return number

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

# database functions

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

if __name__ == '__main__':
    app.run(host = '0.0.0.0')