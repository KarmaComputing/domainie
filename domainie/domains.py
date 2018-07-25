import functools
import requests

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from domainie.db import get_db

bp = Blueprint('domains', __name__, url_prefix=None)

@bp.route('/check', methods=('GET', 'POST'))
def check_availability():
    if request.method == 'POST':

        domain = request.form['domain']

        r = requests.post('https://api.cloudns.net/domains/check-available.json',
                      params = {'auth-id':1697, 'auth-password':'WQ5T\DH5R%mUo',
                                'name':domain, 'tld[]':['co.uk','com']})
        return r.text
        db = get_db()
        error = None
    return render_template('domains/checker.html')
