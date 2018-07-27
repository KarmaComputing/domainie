import functools
import requests
import stripe
from flask import json

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from domainie.db import get_db

bp = Blueprint('domains', __name__, url_prefix=None)

def get_domain_price(tdl, withVAT=True):

    # Get prices and apply margin
    prices = requests.post('https://api.cloudns.net/domains/pricing-list.json',
                           params = {'auth-id':1697, 'auth-password':'WQ5T\DH5R%mUo'}).text
    prices = json.loads(prices)

    price = prices[tdl]['price_registration']
    import pdb;pdb.set_trace()
    return round(price * 1.4, 2)

@bp.route('/check', methods=('GET', 'POST'))
def check_availability():
    if request.method == 'POST':

        domain = request.form['domain']
        # Remove any user provided tlds (e.g. strip .co.uk)
        try:
            domain = domain[0:domain.index('.')]
            session['domain'] = domain
        except ValueError as e:
            pass

        result = json.loads(requests.post('https://api.cloudns.net/domains/check-available.json',
                      params = {'auth-id':1697, 'auth-password':'WQ5T\DH5R%mUo',
                                'name':domain, 'tld[]':['co.uk', 'com']}).text)
        # Get prices and apply margin
        prices = requests.post('https://api.cloudns.net/domains/pricing-list.json',
                               params = {'auth-id':1697, 'auth-password':'WQ5T\DH5R%mUo'}).text
        prices = json.loads(prices)
        # Add prices to result dicts
        result[result.keys()[0]] = [result[result.keys()[0]], {'price': get_domain_price('co.uk') }]
        result[result.keys()[1]] = [result[result.keys()[1]], {'price': get_domain_price('com')}]

        return render_template('domains/register.html', result = result,
                               prices=prices)
    return render_template('domains/checker.html')

@bp.route('/purchase', methods=('GET', 'POST'))
def purchase():
    if request.method == 'POST':

        #Calculate total price
        amount = 0
        domains = request.form.getlist('domains')
        for domain in domains:
            tdl = domain[domain.index('.')+1:] # extracts tld
            price = get_domain_price(tdl)
            price = price + price
        amount = int(price * 100)
        import pdb;pdb.set_trace()

        # Create charge, then register domain(s)
        stripe.api_key = "sk_test_D1dVenFiwWCObU7vUFHbWgdN"
        stripe_token = request.form['stripeToken']
        charge = stripe.Charge.create(
            amount = amount,
            currency='gbp',
            description='Domain Registration',
            source=stripe_token,
        )

        if charge.status == 'succeeded':
            name = request.form['name']
            email = request.form['email']
            telno = request.form['telno']
            company = request.form['company']
            addr1 = request.form['addr1']
            city = request.form['city']
            state = request.form['state']
            zip = request.form['zip']
            result = requests.post('https://api.cloudns.net/domains/order-new-domain.json',
                          params = {'auth-id':1697, 'auth-password':'',
                                    'domain-name':session['domain'], 'tld':'co.uk',
                                    'period':1, 'mail':email, 'name':name,
                                    'company':company, 'address':addr1, 'city':city,
                                    'state':state, 'zip':zip, 'country':'GB',
                                    'telno':telno, 'telnocc':44})

            if 'Success' in result.text:
                # Create DNS Zone for each domain
                domain_name = session['domain'] + '.co.uk'
                result = requests.post('https://api.cloudns.net/dns/register.json', 
                                       params = {'auth-id':1697,
                                                 'auth-password':'abc',
                                                 'domain-name':domain_name,
                                                 'zone-type':'master'})
                if 'Success' in result.text:
                    print "DNS Zone created sucessfully"

            return render_template('domains/thankyou.html')

    return render_template('domains/purchase.html')
