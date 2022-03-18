import websocket
import json
import pickle


# SOCKET gets live stream of candle data
SOCKET = "wss://fstream.binance.com/ws/btcusdt_perpetual@continuousKline_15m"

# store response and save it to data file
def on_message(ws, message):

    # contains asset data
    json_message = json.loads(message)
    
    # enter your desired filepath here
    with open('/home/pi/Documents/Trade/bot/kline_data.dat', 'wb') as f:
        pickle.dump(json_message, f)

# confirmation of open / closed connection
def on_open(ws):

    print('\n---> open\n')

def on_close(ws, close_status, close_message):

    print('\n---> closed\n\n')

# error
def on_error(ws, error):

    print(error)

# ping & pong
def on_ping(ws, message):

    return

def on_pong(ws, message):

    return

# open websocket and run forever
ws = websocket.WebSocketApp(SOCKET, on_open=on_open,
                            on_close=on_close, on_message=on_message, 
                            on_error=on_error, on_ping=on_ping, on_pong=on_pong)

ws.run_forever(ping_interval=240, ping_timeout=120)
