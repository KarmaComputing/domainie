import functools
import requests
import stripe
from flask import json

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from domainie.db import get_db
from flask import current_app as app

bp = Blueprint('domains', __name__, url_prefix=None)

def get_domain_price(tdl, withVAT=True):

    # Get prices and apply margin
    prices = requests.post('https://api.cloudns.net/domains/pricing-list.json',
                           params = {'auth-id':app.config['CLOUDNS_AUTH_ID'], 
                                     'auth-password':app.config['CLOUDNS_AUTH_PASSWORD']
                                    }).text
    prices = json.loads(prices)
    price = prices[tdl]['price_registration']
    price = round(price * 1.4, 2)
    if session.get('discount'):
        price = price * 0.8 #20% discount
    return price

@bp.route('/', methods=('GET', 'POST'), defaults={'path':''})
@bp.route('/<path:path>', methods=('GET', 'POST'))
@bp.route('/check', methods=('GET', 'POST'))
def check_availability(path):
    if 'offer' in path.lower():
        session['discount'] = True
        flash('Congrats! Your 20% discount has been registered.')

    if request.method == 'POST':

        domain = request.form['domain']
        # Remove any user provided tlds (e.g. strip .co.uk)
        try:
            domain = domain[0:domain.index('.')]
        except ValueError as e:
            pass

        result = json.loads(requests.post('https://api.cloudns.net/domains/check-available.json',
                      params = {'auth-id':app.config['CLOUDNS_AUTH_ID'],
                                'auth-password':app.config['CLOUDNS_AUTH_PASSWORD'],
                                'name':domain, 'tld[]':['co.uk', 'com']}).text)
        # Add prices to result dicts
        result[result.keys()[0]] = [result[result.keys()[0]], {'price': get_domain_price('co.uk') }]
        result[result.keys()[1]] = [result[result.keys()[1]], {'price': get_domain_price('com')}]
        stripe_pub_key = app.config['STRIPE_PUB_KEY']
        return render_template('domains/register.html', result = result,
                               stripe_pub_key=stripe_pub_key)
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

        # Create charge, then register domain(s)
        stripe.api_key = app.config['STRIPE_PRIV_KEY']
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
            state = "UK"
            zip = request.form['zip']

            for webaddress in domains:
                tdl = webaddress[webaddress.index('.')+1:] # extracts tld
                domain = webaddress[0:webaddress.index('.')]

                if 'test' not in app.config['STRIPE_PUB_KEY'] and app.config['ENVIRONMENT'] == 'live':
                    print "Buying" + str(domain)
                    print "#"*80
                    result = requests.post('https://api.cloudns.net/domains/order-new-domain.json',
                                  params = {'auth-id':app.config['CLOUDNS_AUTH_ID'], 
                                            'auth-password':app.config['CLOUDNS_AUTH_PASSWORD'],
                                            'domain-name':domain, 'tld':tdl,
                                            'period':1, 'mail':email, 'name':name,
                                            'company':company, 'address':addr1, 'city':city,
                                            'state':state, 'zip':zip, 'country':'GB',
                                            'privacy_protection':1,
                                            'telno':telno, 'telnocc':44})
                    print result.text
                    print "#"*80

                    if 'Success' in result.text:
                        # Create DNS Zone for each domain
                        print "Creating zone"
                        result = requests.post('https://api.cloudns.net/dns/register.json', 
                                               params = {'auth-id':app.config['CLOUDNS_AUTH_ID'],
                                                         'auth-password':app.config['CLOUDNS_AUTH_PASSWORD'],
                                                         'domain-name':''.join([domain, tdl]),
                                                         'zone-type':'master'})
                        print result.text
                        print "#"*80
                        if 'Success' in result.text:
                            print "DNS Zone created sucessfully"
                        # Add default A record
                        print "Creating default A record: '@'"
                        result = requests.post('https://api.cloudns.net/dns/add-record.json', 
                                               params = {'auth-id':app.config['CLOUDNS_AUTH_ID'],
                                                         'auth-password':app.config['CLOUDNS_AUTH_PASSWORD'],
                                                         'domain-name':''.join([domain, tdl]),
                                                         'record-type':'A',
                                                         'host':'@',
                                                         'record':app.config['DEFAULT_A_RECORD_HOST'],
                                                         'ttl':60})
                        print result.text
                        print "#"*80

                        print "Creating default A record: 'www'"
                        result = requests.post('https://api.cloudns.net/dns/add-record.json', 
                                               params = {'auth-id':app.config['CLOUDNS_AUTH_ID'],
                                                         'auth-password':app.config['CLOUDNS_AUTH_PASSWORD'],
                                                         'domain-name':''.join([domain, tdl]),
                                                         'record-type':'A',
                                                         'host':'www',
                                                         'record':app.config['DEFAULT_A_RECORD_HOST'],
                                                         'ttl':60})
                        print result.text
                        print "#"*80


        return render_template('domains/thankyou.html')

    return render_template('domains/purchase.html')
