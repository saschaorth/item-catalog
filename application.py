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

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read()
)['web']['client_id']

engine = create_engine('sqlite:///itemcatalog.db?check_same_thread=False')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/login')
def login():
    """
    Create anti-forgery state token and pass to login.html
    """
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/logout')
def logout():
    """
    Logs the user out and deletes all login_session details.
    """
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
    """
    Get the user.id for a specific email address
    """
    try:
        user = session.query(User)\
            .filter_by(email=email)\
            .one()
        return user.id
    except NoResultFound:
        return None


def add_user(login_session):
    """
    Add a user to the database
    """
    user = User(
        name=login_session['email'],
        email=login_session['email']
    )
    session.add(user)
    session.commit()


@app.route('/gconnect', methods=['POST'])
def gconnect():
    """
    Third party authentication via Google OAuth2.0 plus login
    """

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
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401
        )
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    endpoint = 'https://www.googleapis.com/oauth2/v1/tokeninfo?access_token='
    url = ('{}{}'.format(endpoint, access_token))
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
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401
        )
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401
        )
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')

    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200
        )
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
    """
    Disconnect via Google OAuth2.0
    """
    access_token = login_session.get('access_token')

    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401
        )
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
        response = make_response(
            json.dumps('Failed to revoke token for given user.'), 400
        )
        response.headers['Content-Type'] = 'application/json'
        return response

    return 'logout successful'


@app.route('/')
@app.route('/catalog/')
def show_categories():
    """
    Get all categories and category items and pass them to categories.html
    """
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
    """
    Get all categories, the category items for a specific category and
    the number of those category items and pass them to category_items.html
    """
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
    """
    get a specific item and pass to item.html
    """
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


def ensure_login(func):
    """
    Decorator that makes sure the user is logged in
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'username' not in login_session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


@app.route('/catalog/item/new', methods=['POST', 'GET'])
@ensure_login
def add_item():
    """
    Takes item details from the request form and creates a new item in the
    database
    """
    if request.method == 'POST':

        # ensure all fields are filled with values
        if not request.form['name']:
            flash('Please add an item name')
            return redirect(url_for('add_item'))
        if not request.form['description']:
            flash('Please add a description')
            return redirect(url_for('add_item'))

        new_item = Item(
            category_id=request.form['category'],
            name=request.form['name'],
            description=request.form['description'],
            user_id=login_session['user_id']
        )
        session.add(new_item)
        session.commit()
        flash('New item {} successfully created'.format(new_item.name))
        return redirect(
            url_for('show_category_items', category_id=new_item.category_id)
        )
    else:
        categories = session.query(Category).all()
        return render_template('add_item.html', categories=categories)


@app.route(
    '/catalog/<int:category_id>/item/<int:item_id>/edit',
    methods=['POST', 'GET']
)
@ensure_login
def edit_item(category_id, item_id):
    """
    Takes item details from the request form and updates a specific item
    in the database with those details
    """
    item = session.query(Item)\
        .filter_by(id=item_id)\
        .one()

    item_owner = session.query(User)\
        .filter_by(id=item.user_id)\
        .one()

    # Make sure only the owner of an item has edit rights
    if item_owner.id != login_session['user_id']:
        flash('Only the owner has edit rights for item {}'.format(item.name))
        return redirect(url_for('show_categories'))

    categories = session.query(Category).all()

    if request.method == 'POST':
        if request.form['name']:
            item.name = request.form['name']
        if request.form['description']:
            item.description = request.form['description']
        if request.form['category']:
            item.category_id = request.form['category']

        # ensure all fields are filled with values
        if not request.form['name']:
            flash('Please add an item name')
            return redirect(url_for('edit', category_id=category_id))
        if not request.form['description']:
            flash('Please add a description')
            return redirect(
                url_for('edit_item', category_id=category_id, item_id=item_id)
            )

        session.add(item)
        session.commit()
        flash('Item {} successfully edited'.format(item.name))
        return redirect(
            url_for('show_category_items', category_id=category_id)
        )
    else:
        return render_template(
            'edit_item.html', item=item, categories=categories
        )


@app.route(
    '/catalog/<int:category_id>/item/<int:item_id>/delete',
    methods=['POST', 'GET'])
@ensure_login
def delete_item(category_id, item_id):
    """
    Deletes a specific item from the database.
    """
    item = session.query(Item)\
        .filter_by(id=item_id)\
        .one()

    item_owner = session.query(User)\
        .filter_by(id=item.user_id)\
        .one()

    # Make sure only the owner of an item has delete rights
    if item_owner.id != login_session['user_id']:
        flash('Only the owner has delete rights for item {}'.format(item.name))
        return redirect(url_for('show_categories'))

    if request.method == 'POST':
        session.delete(item)
        session.commit()
        flash('Item {} successfully deleted'.format(item.name))
        return redirect(
            url_for('show_category_items', category_id=category_id)
        )
    else:
        return render_template('delete_item.html', item=item)


@app.route('/catalog/json')
def show_categories_json():
    """
    Gets all categories in json format
    """
    categories = session.query(Category).all()
    return jsonify(categories=[category.serialize for category in categories])


@app.route('/catalog/<int:category_id>/json')
def show_category_items_json(category_id):
    """
    Gets all category items for a specific category in json format
    """
    items = session.query(Item)\
        .filter_by(category_id=category_id)\
        .all()
    return jsonify(categoryItems=[item.serialize for item in items])


@app.route('/catalog/<int:category_id>/item/<int:item_id>/json')
def show_category_item_json(category_id, item_id):
    """
    Gets a specific item in json format
    """
    item = session.query(Item)\
        .filter_by(id=item_id)\
        .filter_by(category_id=category_id)\
        .first()
    return jsonify(categoryItem=[item.serialize])


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
