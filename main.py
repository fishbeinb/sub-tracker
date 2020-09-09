import base64
import os
import datetime
import plaid
import json
import time
from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify, make_response
import requests
import analyze

app = Flask(__name__)


# Fill in your Plaid API keys - https://dashboard.plaid.com/account/keys
PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID', '5e9c7ada0f92430012f55896')
PLAID_SECRET = os.getenv('PLAID_SECRET', '6bfb3cdf4faf2f8617c4258102b116')
PLAID_PUBLIC_KEY = os.getenv('PLAID_PUBLIC_KEY', 'ed2d4d6804bc615766be662b24b3cf')

# PLAID_CLIENT_ID = os.getenv('PLAID_CLIENT_ID', '5f5947044c3aa50010b47ab1')
# PLAID_SECRET = os.getenv('PLAID_SECRET', '278b6a2867a622cb1a58072748a1fc')
# PLAID_PUBLIC_KEY = os.getenv('PLAID_PUBLIC_KEY', 'ed2d4d6804bc615766be662b24b3cf')

# Use 'sandbox' to test with Plaid's Sandbox environment (username: user_good,
# password: pass_good)
# Use `development` to test with live users and credentials and `production`
# to go live
PLAID_ENV = os.getenv('PLAID_ENV', 'development')
# PLAID_PRODUCTS is a comma-separated list of products to use when initializing
# Link. Note that this list must contain 'assets' in order for the app to be
# able to create and retrieve asset reports.
PLAID_PRODUCTS = os.getenv('PLAID_PRODUCTS', 'transactions')

# PLAID_COUNTRY_CODES is a comma-separated list of countries for which users
# will be able to select institutions from.
PLAID_COUNTRY_CODES = os.getenv('PLAID_COUNTRY_CODES', 'US,CA,GB,FR,ES,IE,NL')

# Parameters used for the OAuth redirect Link flow.
#
# Set PLAID_OAUTH_REDIRECT_URI to 'http://localhost:5000/oauth-response.html'
# The OAuth redirect flow requires an endpoint on the developer's website
# that the bank website should redirect to. You will need to whitelist
# this redirect URI for your client ID through the Plaid developer dashboard
# at https://dashboard.plaid.com/team/api.
PLAID_OAUTH_REDIRECT_URI = os.getenv('PLAID_OAUTH_REDIRECT_URI', '');
# Set PLAID_OAUTH_NONCE to a unique identifier such as a UUID for each Link
# session. The nonce will be used to re-open Link upon completion of the OAuth
# redirect. The nonce must be at least 16 characters long.
PLAID_OAUTH_NONCE = os.getenv('PLAID_OAUTH_NONCE', '');

client = plaid.Client(client_id = PLAID_CLIENT_ID, secret=PLAID_SECRET,
                      public_key=PLAID_PUBLIC_KEY, environment=PLAID_ENV, api_version='2019-05-29')

import json
import datetime
import threading
from time import sleep

# from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore, storage
# from google.cloud import storage

import os

def add_from_dict(user_info):
    db = firestore.Client()
    # [START add_from_dict]
    print("A", len(user_info))
    for x in user_info:
      print x#, user_info[x]


@app.route('/')
def index(): 
  return render_template(
    'index.ejs',
    plaid_public_key=PLAID_PUBLIC_KEY,
    plaid_environment=PLAID_ENV,
    plaid_products=PLAID_PRODUCTS,
    plaid_country_codes=PLAID_COUNTRY_CODES,
    plaid_oauth_redirect_uri=PLAID_OAUTH_REDIRECT_URI,
    plaid_oauth_nonce=PLAID_OAUTH_NONCE,
  )


# We store the access_token in memory - in production, store it in a secure
# persistent data store.
access_token = None
# The payment_token is only relevant for the UK Payment Initiation product.
# We store the payment_token in memory - in production, store it in a secure
# persistent data store.
payment_token = None
payment_id = None

# Exchange token flow - exchange a Link public_token for
# an API access_token
# https://plaid.com/docs/#exchange-token-flow
@app.route('/get_access_token', methods=['POST'])
def get_access_token():
  global access_token
  public_token = request.form['public_token']
  try:
    exchange_response = client.Item.public_token.exchange(public_token)
  except plaid.errors.PlaidError as e:
    return jsonify(format_error(e))

  pretty_print_response(exchange_response)
  access_token = exchange_response['access_token']

  return jsonify(exchange_response)

@app.route('/subscriptions', methods=['GET'])
def get_subscriptions():
  all_requests = get_all_transactions() # requests.get("http://127.0.0.1:8080/get_all")
  subscriptions_charges = analyze.run_main_collector(all_requests)
  return jsonify({'error': None, 'subscriptions': subscriptions_charges})

def get_all_transactions():
  start_date = '{:%Y-%m-%d}'.format(datetime.datetime.now() + datetime.timedelta(-3000))
  end_date = '{:%Y-%m-%d}'.format(datetime.datetime.now())
  all_transactions = True
  offset = 0
  all_t = []
  try:
    while all_transactions:
      transactions_response = client.Transactions.get("access-development-8a82d458-6492-41a1-a617-9584c6bf05ae", start_date, end_date, count=500, offset=offset)
      offset = offset + 500
      all_t.extend(transactions_response["transactions"])
      # print transactions_response["transactions"]
      # print(offset, "CC", transactions_response["total_transactions"], transactions_response["total_transactions"] < offset)
      if True or transactions_response["total_transactions"] < offset:
        break
  except plaid.errors.PlaidError as e:
    return jsonify(format_error(e))
  transactions_response["transactions"] = all_t
  return jsonify({'error': None, 'transactions': transactions_response})

def pretty_print_response(response):
  print(json.dumps(response, indent=2, sort_keys=True))

def format_error(e):
  return {'error': {'display_message': e.display_message, 'error_code': e.code, 'error_type': e.type, 'error_message': e.message } }

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)