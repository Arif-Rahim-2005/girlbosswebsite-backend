import re
from decimal import Decimal, InvalidOperation

from flask import request
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import db, User, Product, ProductImage
from services.cloudinary_service import upload_image, delete_image

import logging

logger = logging.getLogger(__name__)


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
        "images": [
            {
                "id": image.id,
                "image_url": image.image_url,
                "public_id": image.public_id,
                "is_primary": image.is_primary,
            }
            for image in product.images
        ],
        "created_at": (
            product.created_at.isoformat()
            if product.created_at else None
        ),
        "updated_at": (
            product.updated_at.isoformat()
            if product.updated_at else None
        ),
        "is_featured": product.is_featured,
    }


class ProductsResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument(
        "product_name",
        type=str,
        required=True,
        help="Product name is required.",
        location="form"

    )
    parser.add_argument(
        "product_description",
        type=str,
        required=True,
        help="Product description is required.",
        location="form"
    )
    parser.add_argument(
        "packaging",
        type=str,
        required=True,
        help="Packaging is required.",
        location="form"
    )
    parser.add_argument(
        "price_per_pack",
        type=str,
        required=True,
        help="Price per pack is required.",
        location="form"
    )

    parser.add_argument(
        "availability",
        type=str,
        required=False,
        default="Available",
        location="form"
    )
    parser.add_argument(
        "is_featured",
        type=str,
        required=False,
        default="false",
        location="form"
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

        if not current_user or current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        
        data = self.parser.parse_args(req=request)
        images = request.files.getlist("images")
        product_name = data["product_name"].strip()
        description = data["product_description"].strip()
        packaging = data["packaging"].strip()
        availability = (data.get("availability") or "Available").strip()
        featured_value = str(data.get("is_featured", "false")).strip().lower()

        if featured_value not in ("true", "false", "1", "0"):
            return {"message": "Invalid featured-product value."}, 400

        is_featured = featured_value in ("true", "1")

        if not all([product_name, description, packaging, availability]):
            return {"message": "Product fields cannot be empty."}, 400

        if not images or any(not image.filename for image in images):
            return {
                "message": "Please upload at least one product image."
            }, 400

        try:
            price = Decimal(data["price_per_pack"])

            if not price.is_finite() or price < 0:
                return {
                    "message": "Price must be a valid non-negative number."
                }, 400

            slug = make_unique_slug(product_name)

        except (InvalidOperation, ValueError):
            return {"message": "Invalid product name or price."}, 400

        uploaded_public_ids = []

        try:
            product = Product(
                product_name=product_name,
                slug=slug,
                product_description=description,
                packaging=packaging,
                price_per_pack=price,
                availability=availability,
                is_featured=is_featured,
            )

            db.session.add(product)
            db.session.flush()

            for index, image_file in enumerate(images):
                result = upload_image(
                    image_file,
                    folder="girlbosswebsite/products"
                )

                uploaded_public_ids.append(result["public_id"])

                product_image = ProductImage(
                    product_id=product.id,
                    image_url=result["image_url"],
                    public_id=result["public_id"],
                    is_primary=(index == 0),
                )

                db.session.add(product_image)

            db.session.commit()

        except Exception as error:
            db.session.rollback()

            print("PRODUCT CREATION ERROR:", repr(error))

            for public_id in uploaded_public_ids:
                try:
                    delete_image(public_id)
                except Exception as cleanup_error:
                    print("CLOUDINARY CLEANUP ERROR:", repr(cleanup_error))

            return {
                "message": "Product creation failed. Check the Flask terminal."
            }, 500

        return {
            "message": "Product and images created successfully.",
            "product": product_to_dict(product),
        }, 201



class ProductImagesResource(Resource):

    @jwt_required()
    def post(self, product_id):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        product = db.session.get(Product, product_id)

        if not product:
            return {"message": "Product not found."}, 404

        images = request.files.getlist("images")

        if not images or any(not image.filename for image in images):
            return {
                "message": "Please select at least one image to upload."
            }, 400

        uploaded_public_ids = []

        try:
            # Check whether this product already has a primary image.
            has_primary = any(
                image.is_primary for image in product.images
            )

            for image_file in images:
                result = upload_image(
                    image_file,
                    folder="girlbosswebsite/products"
                )

                uploaded_public_ids.append(result["public_id"])

                product_image = ProductImage(
                    product_id=product.id,
                    image_url=result["image_url"],
                    public_id=result["public_id"],
                    is_primary=not has_primary
                )

                db.session.add(product_image)

                # Only the first image added to a product becomes primary.
                if not has_primary:
                    has_primary = True

            db.session.commit()

            return {
                "message": "Product images added successfully.",
                "product": product_to_dict(product)
            }, 201

        except Exception:
            db.session.rollback()

            # Clean up Cloudinary files if the database operation f


    @jwt_required()
    def delete(self, product_id, image_id=None):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        product = db.session.get(Product, product_id)

        if not product:
            return {"message": "Product not found."}, 404

        # Delete one image or all images belonging to this product.
        if image_id is not None:
            images_to_delete = [
                image for image in product.images
                if image.id == image_id
            ]

            if not images_to_delete:
                return {
                    "message": "Image not found for this product."
                }, 404
        else:
            images_to_delete = list(product.images)

            if not images_to_delete:
                return {
                    "message": "This product has no images to delete."
                }, 404

        public_ids = [
            image.public_id for image in images_to_delete
        ]

        try:
            deleting_primary = any(
                image.is_primary for image in images_to_delete
            )

            deleted_image_ids = {
                image.id for image in images_to_delete
            }

            replacement_image = None

            if deleting_primary and image_id is not None:
                replacement_image = next(
                    (
                        image for image in product.images
                        if image.id not in deleted_image_ids
                    ),
                    None
                )

            for image in images_to_delete:
                db.session.delete(image)

            if replacement_image:
                replacement_image.is_primary = True

            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()

            return {
                "message": "Unable to delete product image records."
            }, 500

        except SQLAlchemyError:
            db.session.rollback()

            return {
                "message": "Unable to delete product image records."
            }, 500

        # Delete the corresponding files from Cloudinary.
        failed_deletions = []

        for public_id in public_ids:
            try:
                result = delete_image(public_id)

                if result.get("result") not in ("ok", "not found"):
                    failed_deletions.append(public_id)

            except Exception:
                logger.exception(
                    "Failed to delete product image from Cloudinary."
                )
                failed_deletions.append(public_id)

        if failed_deletions:
            return {
                "message": (
                    "Image records were deleted, but some Cloudinary "
                    "files could not be deleted."
                ),
                "failed_image_count": len(failed_deletions),
                "product": product_to_dict(product)
            }, 500

        message = (
            "Product image deleted successfully."
            if image_id is not None
            else "All product images deleted successfully."
        )

        return {
            "message": message,
            "product": product_to_dict(product)
        }, 200



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

        if not current_user or current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        product = db.session.get(Product, product_id)

        if not product:
            return {"message": "Product not found."}, 404

        data = request.form

        try:
            # Update the product name and generate a unique slug.
            if "product_name" in data:
                product_name = data.get("product_name", "").strip()

                if not product_name:
                    return {"message": "Product name cannot be empty."}, 400

                product.product_name = product_name
                product.slug = make_unique_slug(
                    product_name,
                    product_id=product.id
                )

            # Update the description.
            if "product_description" in data:
                description = data.get("product_description", "").strip()

                if not description:
                    return {
                        "message": "Product description cannot be empty."
                    }, 400

                product.product_description = description

            # Update the packaging information.
            if "packaging" in data:
                packaging = data.get("packaging", "").strip()

                if not packaging:
                    return {
                        "message": "Packaging cannot be empty."
                    }, 400

                product.packaging = packaging

            # Update the price.
            if "price_per_pack" in data:
                try:
                    price = Decimal(data.get("price_per_pack", "").strip())
                except (InvalidOperation, AttributeError):
                    return {"message": "Please provide a valid price."}, 400

                if not price.is_finite() or price < 0:
                    return {
                        "message": "Price must be a valid, non-negative number."
                    }, 400

                product.price_per_pack = price

            # Update availability.
            if "availability" in data:
                availability = data.get("availability", "").strip()

                if not availability:
                    return {
                        "message": "Availability cannot be empty."
                    }, 400

                product.availability = availability

            if "is_featured" in data:
                featured_value = data["is_featured"].strip().lower()

                if featured_value not in ("true", "false", "1", "0"):
                    return {"message": "Invalid featured-product value."}, 400

                is_featured = featured_value in ("true", "1")

                product.is_featured = is_featured
                
            db.session.commit()

            return {
                "message": "Product updated successfully.",
                "product": product_to_dict(product)
            }, 200

        except IntegrityError:
            db.session.rollback()
            return {
                "message": "A product with those details already exists."
            }, 409

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "A database error occurred while updating the product."
            }, 500

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

        # Save image IDs before deleting the product.
        public_ids = [
            image.public_id for image in product.images
        ]

        try:
            db.session.delete(product)
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            return {"message": "Unable to delete product."}, 500

        # Delete the associated files from Cloudinary.
        failed_deletions = []

        for public_id in public_ids:
            try:
                result = delete_image(public_id)

                if result.get("result") not in ("ok", "not found"):
                    failed_deletions.append(public_id)

            except Exception:
                logger.exception(
                    "Failed to delete product image from Cloudinary."
                )
                failed_deletions.append(public_id)

        if failed_deletions:
            return {
                "message": (
                    "Product deleted, but some Cloudinary images "
                    "could not be deleted."
                ),
                "failed_image_count": len(failed_deletions)
            }, 500

        return {"message": "Product deleted successfully."}, 200
