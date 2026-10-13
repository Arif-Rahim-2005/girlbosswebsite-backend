import re
from decimal import Decimal, InvalidOperation

from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import db, User, Product


def get_current_user():
    user_id = get_jwt_identity()
    return db.session.get(User, int(user_id))


def generate_slug(product_name):
    slug = product_name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug.strip("-")


def make_unique_slug(product_name, product_id=None):
    base_slug = generate_slug(product_name)

    if not base_slug:
        raise ValueError("Product name must contain letters or numbers.")

    slug = base_slug
    counter = 2

    while True:
        query = Product.query.filter_by(slug=slug)

        if product_id is not None:
            query = query.filter(Product.id != product_id)

        if query.first() is None:
            return slug

        slug = f"{base_slug}-{counter}"
        counter += 1


def product_to_dict(product):
    return {
        "id": product.id,
        "product_name": product.product_name,
        "slug": product.slug,
        "product_description": product.product_description,
        "packaging": product.packaging,
        "price_per_pack": str(product.price_per_pack),
        "availability": product.availability,
        "created_at": (
            product.created_at.isoformat()
            if product.created_at else None
        ),
        "updated_at": (
            product.updated_at.isoformat()
            if product.updated_at else None
        ),
    }


class ProductsResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument(
        "product_name",
        type=str,
        required=True,
        help="Product name is required.",
    )
    parser.add_argument(
        "product_description",
        type=str,
        required=True,
        help="Product description is required.",
    )
    parser.add_argument(
        "packaging",
        type=str,
        required=True,
        help="Packaging is required.",
    )
    parser.add_argument(
        "price_per_pack",
        type=str,
        required=True,
        help="Price per pack is required.",
    )

    parser.add_argument(
        "availability",
        type=str,
        required=False,
        default="Available",
    )

    def get(self):
        products = Product.query.order_by(Product.created_at.desc()).all()

        return {
            "products": [product_to_dict(product) for product in products]
        }, 200

    @jwt_required()
    def post(self):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        data = self.parser.parse_args()

        product_name = data["product_name"].strip()
        description = data["product_description"].strip()
        packaging = data["packaging"].strip()
        availability = data.get("availability") or "Available"

        if not all([product_name, description, packaging]):
            return {"message": "Product fields cannot be empty."}, 400

        try:
            price = Decimal(data["price_per_pack"])

            if not price.is_finite() or price < 0:
                return {"message": "Price must be a valid non-negative number."}, 400

            slug = make_unique_slug(product_name)

        except (InvalidOperation, ValueError):
            return {"message": "Invalid product name or price."}, 400

        product = Product(
            product_name=product_name,
            slug=slug,
            product_description=description,
            packaging=packaging,
            price_per_pack=price,
            availability=availability,
        )

        try:
            db.session.add(product)
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            return {"message": "A product with these details already exists."}, 409

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Unable to save product."}, 500

        return {
            "message": "Product created successfully.",
            "product": product_to_dict(product),
        }, 201


class ProductResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument("product_name", type=str)
    parser.add_argument("product_description", type=str)
    parser.add_argument("packaging", type=str)
    parser.add_argument("price_per_pack", type=str)
    parser.add_argument("availability", type=str)

    def get(self, product_id):
        product = db.session.get(Product, product_id)

        if not product:
            return {"message": "Product not found."}, 404

        return {"product": product_to_dict(product)}, 200

    @jwt_required()
    def patch(self, product_id):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        product = db.session.get(Product, product_id)

        if not product:
            return {"message": "Product not found."}, 404

        data = self.parser.parse_args()

        if data["product_name"] is not None:
            product_name = data["product_name"].strip()

            if not product_name:
                return {"message": "Product name cannot be empty."}, 400

            product.product_name = product_name

            try:
                product.slug = make_unique_slug(
                    product_name,
                    product_id=product.id,
                )
            except ValueError as error:
                return {"message": str(error)}, 400

        for field in (
            "product_description",
            "packaging",
            "availability",
        ):
            value = data.get(field)

            if value is not None:
                value = value.strip()

                if not value and field != "availability":
                    return {"message": f"{field} cannot be empty."}, 400

                setattr(product, field, value)

        if data["price_per_pack"] is not None:
            try:
                price = Decimal(data["price_per_pack"])

                if not price.is_finite() or price < 0:
                    return {"message": "Price must be a valid non-negative number."}, 400

                product.price_per_pack = price

            except InvalidOperation:
                return {"message": "Invalid price."}, 400

        try:
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            return {"message": "Could not update product due to a data conflict."}, 409

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Unable to update product."}, 500

        return {
            "message": "Product updated successfully.",
            "product": product_to_dict(product),
        }, 200

    @jwt_required()
    def delete(self, product_id):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        product = db.session.get(Product, product_id)

        if not product:
            return {"message": "Product not found."}, 404

        try:
            db.session.delete(product)
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Unable to delete product."}, 500

        return {"message": "Product deleted successfully."}, 200