from sqlalchemy import MetaData
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_bcrypt import generate_password_hash, check_password_hash


convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(metadata=metadata)


# -------------------------
# USER
# -------------------------

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(20), nullable=False, default="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# -------------------------
# PRODUCT
# -------------------------

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    product_description = db.Column(db.Text, nullable=False)
    packaging = db.Column(db.String(100), nullable=False)
    price_per_pack = db.Column(db.Numeric(10, 2), nullable=False)
    availability = db.Column(db.String(80), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    is_featured = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false()
    )
    images = db.relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan"
    )


# -------------------------
# PRODUCT IMAGES
# -------------------------

class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    image_url = db.Column(db.String(500), nullable=False)
    public_id = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product", back_populates="images")


# -------------------------
# POSTS
# -------------------------

class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="draft"
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    images = db.relationship(
        "PostImage",
        back_populates="post",
        cascade="all, delete-orphan"
    )


# -------------------------
# POST IMAGES
# -------------------------

class PostImage(db.Model):
    __tablename__ = "post_images"

    id = db.Column(db.Integer, primary_key=True)

    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=False
    )

    image_url = db.Column(db.String(500), nullable=False)
    public_id = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship("Post", back_populates="images")


# -------------------------
# ADVERTISEMENTS
# -------------------------

class Advertisement(db.Model):
    __tablename__ = "advertisements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    image_alt_text = db.Column(db.String(255), nullable=True)
    destination_url = db.Column(db.String(500), nullable=True)

    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="draft"
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    images = db.relationship(
        "AdvertisementImage",
        back_populates="advertisement",
        cascade="all, delete-orphan"
    )


# -------------------------
# ADVERTISEMENT IMAGES
# -------------------------

class AdvertisementImage(db.Model):
    __tablename__ = "advertisement_images"

    id = db.Column(db.Integer, primary_key=True)

    advertisement_id = db.Column(
        db.Integer,
        db.ForeignKey("advertisements.id"),
        nullable=False
    )

    image_url = db.Column(db.String(500), nullable=False)
    public_id = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    advertisement = db.relationship(
        "Advertisement",
        back_populates="images"
    )
