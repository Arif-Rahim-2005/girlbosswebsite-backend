from sqlalchemy import MetaData
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_bcrypt import generate_password_hash, check_password_hash
import re


convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(metadata=metadata)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        nullable=False
    )

    password_hash = db.Column(
        db.String(128),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="user"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    product_name = db.Column(
        db.String(120),
        nullable=False
    )

    slug = db.Column(
        db.String(140),
        unique=True,
        nullable=False,
        index=True
    )

    product_description = db.Column(
        db.Text,
        nullable=False
    )

    packaging = db.Column(
        db.String(100),
        nullable=False
    )

    price_per_pack = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )
    
    availability = db.Column(
        db.String(80),
        nullable=True
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )