import json
import os
from datetime import datetime
from typing import Dict, List

import mysql.connector
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, request
from flask_mail import Mail, Message

load_dotenv()
# database config
config = {
    'user': 'root',
    'password': 'root',
    'host': 'db',
    'port': '3306',
    'database': 'crypto'
}

app = Flask(__name__)
# mailer config
app.config['MAIL_SERVER'] = 'smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USERNAME'] = os.environ['MAIL_USERNAME']
app.config['MAIL_PASSWORD'] = os.environ['MAIL_PASSWORD']
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)


def get_pagination_url(date, limit, offset):
    return "http://localhost:5000/api/prices/btc?date=" + \
        date+"&offset="+str(offset)+"&limit="+str(limit)


def get_query(select, where, pagination):
    return "SELECT "+select+" FROM prices where "+where+" "+pagination


def prices(date, offset, limit) -> List[Dict]:

    if offset is None:
        offset = "0"
    if limit is None:
        limit = "100"
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    datetime_obj = datetime.strptime(date, '%d-%m-%Y')

    where = "created_at between '" + datetime_obj.strftime(
        "%Y-%m-%d 00:00:00")+"' and '"+datetime_obj.strftime("%Y-%m-%d 23:59:59")+"'"

    cursor.execute(get_query("name,price,created_at", where,"limit "+limit+" offset "+offset))
    results = [{"coin": name, "price": float(price), "timestamp": str(
        created_at)} for (name, price, created_at) in cursor]
  
    cursor.execute(get_query("count(name) as count", where,""))
    total = cursor.fetchone() # fetch total enteries
    
    current = get_pagination_url(date, offset, limit)
    next = get_pagination_url(date, int(offset)+int(limit), limit)

    if int(offset)+int(limit) > total[0]:
        next = None
    cursor.close()
    connection.close()

    return {"count": total[0], "next": next, "current": current, "data": results}


@app.route('/api/prices/btc')
def btc_prices() -> str:
    date = request.args.get('date')
    response = app.response_class(
        response=json.dumps(prices(
            date, request.args.get('offset'), request.args.get('limit'))),
        status=200,
        mimetype='application/json'
    )

    return response

# fetch bitcoin price 
def get_bitcoin_price():
    r = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_last_updated_at=true&precision=2")
    return r.json()


def send_mail(text):
    EMAIL_ID = os.environ['EMAIL_ID']
    msg = Message("Hello",
                  sender="from@example.com",
                  recipients=[EMAIL_ID])
    msg.body = text
    with app.app_context():
        mail.send(msg)


def update_btc_price():
    print("running cron...")
    connection = mysql.connector.connect(**config)
    MIN_PRICE = int(os.environ['MIN_PRICE'])
    MAX_PRICE = int(os.environ['MAX_PRICE'])
    cursor = connection.cursor()
    bitcoin_api_response = get_bitcoin_price()
    bitcoin_price = bitcoin_api_response['bitcoin']['usd']
    
    if bitcoin_price < MIN_PRICE:
        send_mail("Bitcoin price has gone below to the minimum threshold.\n Minimum Threshold: "+ str(MIN_PRICE) +"\n Current Price: "+str(bitcoin_price))
    if bitcoin_price > MAX_PRICE:
        send_mail("Bitcoin price has gone above to the maximum threshold.\n Maximum Threshold: "+ str(MAX_PRICE) +"\n Current Price: "+str(bitcoin_price))
    cursor.execute(
        "INSERT INTO prices (name, price) VALUES ('bitcoin', "+str(bitcoin_price)+")")
    connection.commit()
    cursor.close()
    connection.close()


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    job = scheduler.add_job(update_btc_price, 'interval', seconds=30)
    scheduler.start()
    app.run(host='0.0.0.0')
