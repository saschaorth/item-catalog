from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from models import (
    Base,
    User,
    Category,
    Item
)
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    make_response,
    jsonify
)
from flask import session as login_session
import random
import string
import json
import requests
from oauth2client.client import (
    flow_from_clientsecrets,
    FlowExchangeError
)
import httplib2
from functools import wraps

app = Flask(__name__)

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']

engine = create_engine('sqlite:///itemcatalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/')
@app.route('/catalog/')
def show_categories():
    categories = session.query(Category).all()

    category_items = session.query(Item)\
        .order_by(desc(Item.id))\
        .limit(4)\
        .all()

    return render_template(
        'categories.html',
        categories=categories,
        category_items=category_items
    )


@app.route('/catalog/<int:category_id>/')
def show_category_items(category_id):
    categories = session.query(Category).all()

    category = session.query(Category)\
        .filter_by(id=category_id)\
        .one()

    category_items = session.query(Item)\
        .filter_by(category_id=category_id)\
        .all()

    number_of_category_items = len(category_items)

    return render_template(
        'category_items.html',
        categories=categories,
        category=category,
        category_items=category_items,
        number_of_category_items=number_of_category_items
    )


@app.route('/catalog/<int:category_id>/item/<int:item_id>')
def show_item(category_id, item_id):
    item = session.query(Item)\
        .filter_by(id=item_id)\
        .one()

    category = session.query(Category)\
        .filter_by(id=category_id)\
        .one()

    return render_template(
        'item.html',
        category=category,
        item=item
    )


# Make sure the user is logged in
def ensure_login(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'username' not in login_session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


@app.route('/catalog/<int:category_id>/item/new', methods=['POST', 'GET'])
@ensure_login
def add_item(category_id):
    if request.method == 'POST':

        if not request.form['name']:
            flash('Please add an item name')
            return redirect(url_for('add_item', category_id=category_id))

        if not request.form['description']:
            flash('Please add a description')
            return redirect(url_for('add_item', category_id=category_id))

        new_item = Item(
            category_id=category_id,
            name=request.form['name'],
            description=request.form['description'],
            user_id=login_session['user_id']
        )
        session.add(new_item)
        session.commit()
        flash('New item {} successfully created'.format(new_item.name))
        return redirect(url_for('show_category_items', category_id=category_id))
    else:
        return render_template('add_item.html')


@app.route('/login')
def login():
    # Create anti-forgery state token
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/logout')
def logout():

    if login_session['provider'] == 'google':
        gdisconnect()
        del login_session['access_token']
        del login_session['gplus_id']

    del login_session['username']
    del login_session['email']
    del login_session['user_id']
    del login_session['provider']

    flash('You have successfully logged out')

    return redirect(url_for('show_categories'))


def get_user_id(email):
    try:
        user = session.query(User)\
            .filter_by(email=email)\
            .one()
        return user.id
    except NoResultFound:
        return None


def add_user(login_session):
    user = User(
        name=login_session['email'],
        email=login_session['email']
    )
    session.add(user)
    session.commit()


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate anti-forgery state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={}'.format(access_token))
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')

    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()
    login_session['username'] = data['email']
    login_session['email'] = data['email']
    login_session['provider'] = 'google'

    # Get or add user_id
    user_id = get_user_id(data['email'])
    if not user_id:
        add_user(login_session)
        user_id = get_user_id(data['email'])
    login_session['user_id'] = user_id

    flash("You have successfully logged in")

    return 'login successful'


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')

    if access_token is None:
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

    return 'logout successful'


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
