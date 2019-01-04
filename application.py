from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from models import (
    Base,
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

app = Flask(__name__)

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
