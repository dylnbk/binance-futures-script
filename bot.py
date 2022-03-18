import os
import pickle
import time
import psutil
import datetime
import numpy
import talib
import subprocess
from binance.client import Client
from binance.enums import *


# launch data script, add your file path here
data_connection = "python3 /home/pi/Documents/Trade/data/data.py"

# file path for data stream
data_path = "kline_data.dat"

API_KEY, API_SECRET = 123456789, 123456789

# get API key and secret
client = Client(API_KEY, API_SECRET)

# asset pair
TRADE_TICK = 'BTCUSDT'

# USD balance
balance = 100

# timestamp
timestamp = datetime.datetime.now()

# profit / loss
pnl = 0.0
pnl_usd = 0.0

# position value
position_value = 0

# once in position, keeps track of the highest price
low_price = 0
high_price = 0

# stoploss
stop_loss_short = 10000
stop_loss_long = 0

# number of trades taken
trade_total = 0

# average entry price
entry_av = 0

# RSI variables
RSI_PERIOD = 0
RSI_OVERBOUGHT = 0
RSI_OVERSOLD = 0

# how much asset to buy
TRADE_AMOUNT = 0.0

# order id
order_id = 0

# average entry
entry_price = 0.0

# quantity
qty = 0.0

# short / long tracking
in_short = False
in_long = False

# trend
trend = True

# tracks if program has been prev loaded in current session
program_started = False

# candle data
closes = []
highs = []
lows = []

# buy history
buys = []

# upper and lower bands for ATR, average true range
u_band = []
l_band = []

# asset in a trend, True / False
t_value = []

# check if script is running and return its PID
def is_running(script):
    
    for q in psutil.process_iter():

        if q.name().startswith('python3'):

            if len(q.cmdline())>1 and script in q.cmdline()[1] and q.pid !=os.getpid():

                pid = str(q.pid)

                return pid

    return False

# kill any PID
def kill(name):

    pid = is_running(name)
    os.system(f"kill -9 {pid}")

    return True

# create a connection to binance data, 'data_connection' variable should be passed here
def connect(connection):

    global closes
    global highs
    global lows
    
    # open a connection
    try:
        subprocess.Popen(connection, shell=True)
        
    except:
        print("error establishing connection")

    # load historical data
    try:

        # get the last x candles from binance
        KLINES = client.futures_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_15MINUTE, "24 hours ago UTC")
        index = 0

        # if program has previously ran, replace historical data
        if program_started:

            for x in KLINES:
                closes[index] = float(x[4])
                highs[index] = float(x[2])
                lows[index] = float(x[3])
                index += 1
                
        # else create a new bank of closes, highs & lows
        else:

            for x in KLINES:
                closes.append(float(x[4]))
                highs.append(float(x[2]))        
                lows.append(float(x[3])) 
                
    
    except Exception as e:
        print("error loading historical data")

    return True

# checks required order precision 
def get_quantity_precision(currency_symbol):    

    info = client.futures_exchange_info() 
    info = info['symbols']

    for x in range(len(info)):

        if info[x]['symbol'] == currency_symbol:

            return info[x]['quantityPrecision']

    return None

# get the required order precision
precision = get_quantity_precision(TRADE_TICK)

# find the entry average
def average(a, n):

    sum = 0

    for i in range(n):
        sum += a[i]

    return sum/n

# calculates the trend
def supertrend(h, l, c, a, atr_multiplier=2):

    global u_band
    global l_band
    global t_value

    # if the program has previously run, replace existing bank of data
    if program_started:

        # calculate the upper, lower band and set trend variable
        for x in range(len(h)):

            hl = (h[x] + l[x]) / 2
            upperband = hl + (atr_multiplier * a[x])
            lowerband = hl - (atr_multiplier * a[x])

            # add results to array
            u_band[x] = upperband
            l_band[x] = lowerband
            t_value[x] = True
    
    # create a new bank of data
    else:

        # calculate the upper, lower band and set trend variable
        for x in range(len(h)):

            hl = (h[x] + l[x]) / 2
            upperband = hl + (atr_multiplier * a[x])
            lowerband = hl - (atr_multiplier * a[x])

            # add results to array
            u_band.append(upperband)
            l_band.append(lowerband)
            t_value.append(True)

    # calculate trend band and supertrend signal 
    for current in range(1, len(u_band)):

        previous = current - 1

        # if the close is greater than the upper band, trend is True. price below lower band, trend is False
        if c[current] > u_band[previous]:
            t_value[current] = True
            
        elif c[current] < l_band[previous]:
            t_value[current] = False
        
        # price between bands, trend remains the same
        else:
            t_value[current] = t_value[previous]

            # trend is True and the lower band is decreasing, set lower band to previous value = lower band stays flat
            if t_value[current] and l_band[current] < l_band[previous]:
                l_band[current] = l_band[previous]

            # trend is False and the upper band is increasing, set upper band to previous value = upper band stays flat
            if not t_value[current] and u_band[current] > u_band[previous]:
                u_band[current] = u_band[previous]

    # return True / False
    return t_value[current]

# send a buy order to binance
def order(side, quantity, symbol, positionSide, order_type=FUTURE_ORDER_TYPE_MARKET):

    global qty
    global entry_price

    # create order and print a confirmation
    try:     
        print("\n---> sending order")
        order = client.futures_create_order(symbol=symbol, side=side, type=order_type, 
                                            positionSide=positionSide, quantity=quantity)
        order_id = int(order['orderId'])
        order_info = client.futures_get_order(symbol=TRADE_TICK, orderId=order_id)
        entry_price = float(order_info["avgPrice"])
        qty = float(order_info["executedQty"])
        print(f"\n\n---> completed {qty} @ ${entry_price}")

    except Exception as e:

        print(f"error - {e}")

        return False

    return True 

# main script
while True:

    # load from data file
    try:
        json_message = pickle.load(open(data_path, "rb"))
        
    except:
        continue 
    
    # load time stamps
    timestamp = datetime.datetime.now()
    t_a = timestamp + datetime.timedelta(minutes = -1.5)
    timestamp_b = datetime.datetime.fromtimestamp(json_message['E']/1000)

    # check that data from binance is still being recieved on time
    if timestamp_b > t_a:
        
        # get candle data from live stream
        candle = json_message['k']

        # is the candle closed?
        candle_closed = candle['x']

        # the price at close, high and low
        close = float(candle['c'])
        high = float(candle['h'])
        low = float(candle['l'])

         # when in a trade, log high/low price
        if in_short and close < low_price:
            low_price = close
            print(f"\n---> low price reset @ {low_price}")

        elif in_long and close > high_price:
            high_price = close
            print(f"\n---> high price reset @ {high_price}")
        
        # calculate stop loss & profit / loss
        if trade_total > 0:
            
            # profit & loss
            if in_short:

                # pnl calculation for USD
                pnl_usd = round((entry_av*TRADE_AMOUNT)-(close*TRADE_AMOUNT), 2)

                # pnl calc for %
                pnl = round((pnl_usd/(entry_av*TRADE_AMOUNT))*100, 2)      
                
                position_value = round((entry_av*TRADE_AMOUNT)+pnl_usd, 2)
            
            elif in_long:

                # pnl calculation for USD
                pnl_usd = round((close*TRADE_AMOUNT)-(entry_av*TRADE_AMOUNT), 2)

                # pnl calc for %
                pnl = round((pnl_usd/(entry_av*TRADE_AMOUNT))*100, 2)      
                
                position_value = round((entry_av*TRADE_AMOUNT)+pnl_usd, 2)
        
            # stop loss
            if in_short:

                # trailing at the set targets
                if low_price < entry_av*0.99 and low_price > entry_av*0.97:
                    stop_loss_short = low_price+(low_price*0.02)
                
                elif low_price < entry_av*0.97:
                    stop_loss_short = low_price+(low_price*0.001)
                
                # minimum stop loss
                else:
                    stop_loss_short = u_band[-1]+(u_band[-1]*0.01)

            elif in_long:

                # trailing at the set targets
                if high_price > entry_av*1.01 and high_price < entry_av*1.04:
                    stop_loss_long = high_price-(high_price*0.02)

                elif high_price > entry_av*1.04:
                    stop_loss_long = high_price-(high_price*0.01)

                # minimum stop loss
                else:
                    stop_loss_long = l_band[-1]-(l_band[-1]*0.01)

        # calculate indicators, update arrays and print info when candle closes    
        if candle_closed:

            # adds the last candle close data to arrays
            closes.append(close)
            highs.append(high)
            lows.append(low)
            closes.pop(0)
            highs.pop(0)
            lows.pop(0)

            # convert to numpy arrays
            np_closes = numpy.array(closes)
            np_highs = numpy.array(highs)
            np_lows = numpy.array(lows)

            # send data to calculate ATR, RSI and SMA values 
            atr = talib.ATR(np_highs, np_lows, np_closes, timeperiod=20)

            '''
            rsi = talib.RSI(np_closes, RSI_PERIOD)
            sma = talib.SMA(np_closes, timeperiod=21)

            # get the last values for ATR, RSI, SMA & last close
            last_sma = sma[-1]
            last_rsi = rsi[-1]
            last_atr = atr[-1]
            last_close = closes[-1]
            '''
            
            # calculate trend indicator
            trend = supertrend(highs, lows, closes, atr)

            # needed to stop multiple close candles being added to the list of closes
            time.sleep(1)

            # flag that the program has a bank of variables initialized
            program_started = True

            # print info
            print("\n\n-------------------------")
            print(f"---> upper band @ {round(u_band[-1], 2)}\n---> lower band @ {round(l_band[-1], 2)}")
            print("-------------------------")   
            print(f"\n\n---> last candle closed @ ${close}")
            print(f"\n---> {timestamp}")  
            print(f"\n---> trend @ {trend}\n")
            print(f"\n---> average entry @ ${entry_av}")
            print(f"\n---> current position value @ ${position_value}")
            print(f"\n---> PNL @ ${pnl_usd} - {pnl}%\n")

            if in_short:
                print(f"\n---> stop loss @ ${stop_loss_short}")
            
            elif in_long:
                print(f"\n---> stop loss @ ${stop_loss_long}")
        
        # if a candle has closed, data can now be used to generate indicators and check buy / sell conditions
        if program_started:

            # if the price falls below the stop loss, create sell order
            if (not trend and t_value[-2]) or close < stop_loss_long:

                # when in a long, sell
                if in_long:

                    # set the amount, rounded to the required precision
                    TRADE_AMOUNT = qty

                    print("\n---> sell! sell! sell!")
                    
                    # create order
                    order_succeeded = order(SIDE_SELL, TRADE_AMOUNT, TRADE_TICK, "LONG")

                    time.sleep(1)

                    # if the sell order is successful reset variables
                    if order_succeeded:
                        in_long = False
                        balance = position_value
                        position_value = 0
                        trade_total = 0
                        stop_loss_long = 0
                        entry_av = 0
                        pnl = 0.0
                        pnl_usd = 0.0
                        high_price = 0
                        TRADE_AMOUNT = 0
                        buys.clear()

                # open a short    
                if not in_short:
                    
                    print(f"\n---> short! short! short!")
                    
                    # get the calculated trade amount
                    TRADE_AMOUNT = float(round(balance/close, precision))     
                    
                    # create order
                    order_succeeded = order(SIDE_BUY, TRADE_AMOUNT, TRADE_TICK, "SHORT")

                    time.sleep(1)

                    # if successful add details to array, calculate average entry / high price, count number of trades
                    if order_succeeded:
                        in_short = True
                        buys.append(entry_price)
                        entry_av = average(buys, len(buys))
                        low_price = entry_av
                        trade_total +=1
                    
            # check buy conditions and if True create an order
            if (trend and not t_value[-2]) or close > stop_loss_short:

                # check if in a short, close
                if in_short:

                    # set the amount, rounded to the required precision
                    TRADE_AMOUNT = qty

                    print("\n---> close! close! close!")
                    
                    # create order
                    order_succeeded = order(SIDE_SELL, TRADE_AMOUNT, TRADE_TICK, "SHORT")

                    time.sleep(1)

                    # if the sell order is successful reset variables
                    if order_succeeded:
                        balance = position_value
                        in_short = False
                        position_value = 0
                        stop_loss_short = 10000
                        trade_total = 0
                        low_price = 0
                        TRADE_AMOUNT = 0
                        pnl_usd = 0.0
                        pnl = 0.0
                        entry_av = 0
                        buys.clear()

                # create a long position    
                if not in_long:    

                    print(f"\n---> buy! buy! buy!")

                    # get the calculated trade amount
                    TRADE_AMOUNT = float(round(balance/close, precision))     
                    
                    # create order
                    order_succeeded = order(SIDE_BUY, TRADE_AMOUNT, TRADE_TICK, "LONG")

                    time.sleep(1)

                    # if successful add details to array, calculate average entry / high price, count number of trades
                    if order_succeeded:
                        in_long = True
                        buys.append(entry_price)
                        entry_av = average(buys, len(buys))
                        high_price = entry_av
                        trade_total += 1

    # if the candle data is no longer in time                   
    else:

        # kill existing websocket connection
        if is_running("data.py"):
            
            kill("data.py")

        # reconnect to the websocket       
        connect(data_connection)

        time.sleep(10)
