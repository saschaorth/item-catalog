from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# from sqlalchemy_utils import database_exists, drop_database, create_database

from models import Category, Item, User, Base

engine = create_engine('sqlite:///itemcatalog.db')

# Base.metadata.drop_all(engine)
# Base.metadata.create_all(engine)

Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# users
user1 = User(name="test", email="test@web.de")
session.add(user1)
session.commit()

# berlin
category1 = Category(name="berlin", user_id=1)

session.add(category1)
session.commit()

item1 = Item(name="kreuzberg", user_id=1, description="my kiez", category=category1)

session.add(item1)
session.commit()

item2 = Item(name="neukoelln", user_id=1,  description="my old kiez", category=category1)

session.add(item2)
session.commit()

item3 = Item(name="friedrichshain", user_id=1, description="my work kiez", category=category1)

session.add(item3)
session.commit()

# khruangbin
category2 = Category(name="khruangbin", user_id=1)

session.add(category2)
session.commit()

item1 = Item(name="mark", user_id=1, description="plays guitar", category=category2)

session.add(item1)
session.commit()

item2 = Item(name="laura", user_id=1,  description="plays base", category=category2)

session.add(item2)
session.commit()

item3 = Item(name="donald", user_id=1, description="plays drums", category=category2)

session.add(item3)
session.commit()
