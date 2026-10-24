import re
import logging

from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import db, User, Post, PostImage
from resources.product import get_current_user
from services.cloudinary_service import upload_image, delete_image


logger = logging.getLogger(__name__)


def generate_post_slug(title):
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug.strip("-")


def make_unique_post_slug(title, post_id=None):
    base_slug = generate_post_slug(title)

    if not base_slug:
        raise ValueError("Post title must contain letters or numbers.")

    slug = base_slug
    counter = 2

    while True:
        query = Post.query.filter_by(slug=slug)

        if post_id is not None:
            query = query.filter(Post.id != post_id)

        if query.first() is None:
            return slug

        slug = f"{base_slug}-{counter}"
        counter += 1


def post_to_dict(post):
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "content": post.content,
        "status": post.status,
        "images": [
            {
                "id": image.id,
                "image_url": image.image_url,
                "public_id": image.public_id,
            }
            for image in post.images
        ],
        "created_at": (
            post.created_at.isoformat()
            if post.created_at else None
        ),
        "updated_at": (
            post.updated_at.isoformat()
            if post.updated_at else None
        ),
    }


class PostsResource(Resource):

    def get(self):
        # Public visitors can see published posts.
        # Admins can retrieve drafts through the separate admin endpoint
        # we can add later if needed.
        posts = (
            Post.query
            .filter_by(status="published")
            .order_by(Post.created_at.desc())
            .all()
        )

        return {
            "posts": [post_to_dict(post) for post in posts]
        }, 200

    @jwt_required()
    def post(self):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        status = request.form.get("status", "draft").strip().lower()
        images = request.files.getlist("images")

        if not title or not content:
            return {
                "message": "Title and content are required."
            }, 400

        if status not in ("draft", "published"):
            return {
                "message": "Status must be 'draft' or 'published'."
            }, 400

        if any(not image.filename for image in images):
            return {
                "message": "Please select valid image files."
            }, 400

        try:
            slug = make_unique_post_slug(title)
        except ValueError as error:
            return {"message": str(error)}, 400

        uploaded_public_ids = []

        try:
            post = Post(
                title=title,
                slug=slug,
                content=content,
                status=status,
            )

            db.session.add(post)
            db.session.flush()

            for image_file in images:
                result = upload_image(
                    image_file,
                    folder="girlbosswebsite/posts"
                )

                uploaded_public_ids.append(result["public_id"])

                db.session.add(
                    PostImage(
                        post_id=post.id,
                        image_url=result["image_url"],
                        public_id=result["public_id"],
                    )
                )

            db.session.commit()

            return {
                "message": "Post created successfully.",
                "post": post_to_dict(post),
            }, 201

        except Exception:
            db.session.rollback()

            for public_id in uploaded_public_ids:
                try:
                    delete_image(public_id)
                except Exception:
                    logger.exception(
                        "Failed to clean up Cloudinary image %s",
                        public_id
                    )

            logger.exception("Post creation failed.")

            return {
                "message": "Post creation failed. Check the Flask terminal."
            }, 500


class PostResource(Resource):

    def get(self, post_id):
        post = db.session.get(Post, post_id)

        if not post or post.status != "published":
            return {"message": "Post not found."}, 404

        return {"post": post_to_dict(post)}, 200


    @jwt_required()
    def patch(self, post_id):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        post = db.session.get(Post, post_id)

        if not post:
            return {"message": "Post not found."}, 404

        data = request.form

        if not data:
            return {
                "message": "Please provide at least one field to update."
            }, 400

        if "title" in data:
            title = data.get("title", "").strip()

            if not title:
                return {"message": "Title cannot be empty."}, 400

            try:
                post.slug = make_unique_post_slug(
                    title,
                    post_id=post.id
                )
            except ValueError as error:
                return {"message": str(error)}, 400

            post.title = title

        if "content" in data:
            content = data.get("content", "").strip()

            if not content:
                return {"message": "Content cannot be empty."}, 400

            post.content = content

        if "status" in data:
            status = data.get("status", "").strip().lower()

            if status not in ("draft", "published"):
                return {
                    "message": "Status must be 'draft' or 'published'."
                }, 400

            post.status = status

        try:
            db.session.commit()

            return {
                "message": "Post updated successfully.",
                "post": post_to_dict(post)
            }, 200

        except IntegrityError:
            db.session.rollback()
            return {
                "message": "A post with those details already exists."
            }, 409

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "A database error occurred while updating the post."
            }, 500


    @jwt_required()
    def delete(self, post_id):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        post = db.session.get(Post, post_id)

        if not post:
            return {"message": "Post not found."}, 404

        # Save the Cloudinary IDs before deleting the database records.
        public_ids = [image.public_id for image in post.images]

        try:
            db.session.delete(post)
            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "Unable to delete post from the database."
            }, 500

        # The database deletion succeeded. Now remove the Cloudinary files.
        failed_deletions = []

        for public_id in public_ids:
            try:
                result = delete_image(public_id)

                if result.get("result") not in ("ok", "not found"):
                    failed_deletions.append(public_id)

            except Exception:
                failed_deletions.append(public_id)

        if failed_deletions:
            return {
                "message": (
                    "Post deleted from the database, but some Cloudinary "
                    "images could not be deleted."
                ),
                "failed_image_count": len(failed_deletions)
            }, 500

        return {
            "message": "Post and associated images deleted successfully."
        }, 200



class PostImagesResource(Resource):

    @jwt_required()
    def post(self, post_id, image_id=None):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        post = db.session.get(Post, post_id)

        if not post:
            return {"message": "Post not found."}, 404

        images = request.files.getlist("images")
        mode = request.form.get("mode", "add").strip().lower()

        if mode not in ("add", "replace_selected", "replace_all"):
            return {
                "message": (
                    "Mode must be 'add', 'replace_selected', or 'replace_all'."
                )
            }, 400

        if not images or any(not image.filename for image in images):
            return {
                "message": "Please select at least one image."
            }, 400

        selected_ids = []

        if mode == "replace_selected":
            raw_ids = request.form.getlist("image_ids")

            if not raw_ids:
                return {
                    "message": (
                        "Provide at least one image_id to replace."
                    )
                }, 400

            try:
                selected_ids = list({int(value) for value in raw_ids})
            except ValueError:
                return {
                    "message": "Image IDs must be integers."
                }, 400

            existing_ids = {image.id for image in post.images}

            if not set(selected_ids).issubset(existing_ids):
                return {
                    "message": "One or more image IDs do not belong to this post."
                }, 400

        if mode == "replace_all" and not post.images:
            # Replacing an empty image collection is equivalent to adding.
            mode = "add"

        images_to_remove = []

        if mode == "replace_selected":
            images_to_remove = [
                image for image in post.images
                if image.id in selected_ids
            ]
        elif mode == "replace_all":
            images_to_remove = list(post.images)

        old_public_ids = [
            image.public_id for image in images_to_remove
        ]

        uploaded_public_ids = []

        try:
            # Upload new images first so existing images remain intact
            # if an upload fails.
            new_records = []

            for image_file in images:
                result = upload_image(
                    image_file,
                    folder="girlbosswebsite/posts"
                )

                uploaded_public_ids.append(result["public_id"])

                new_records.append(
                    PostImage(
                        post_id=post.id,
                        image_url=result["image_url"],
                        public_id=result["public_id"]
                    )
                )

            for old_image in images_to_remove:
                db.session.delete(old_image)

            for new_image in new_records:
                db.session.add(new_image)

            db.session.commit()

        except Exception:
            db.session.rollback()

            for public_id in uploaded_public_ids:
                try:
                    delete_image(public_id)
                except Exception:
                    logger.exception(
                        "Failed to clean up Cloudinary image %s",
                        public_id
                    )

            logger.exception("Post image operation failed.")

            return {
                "message": "Unable to update post images."
            }, 500

        # Database changes succeeded. Now remove replaced files from Cloudinary.
        failed_deletions = []

        for public_id in old_public_ids:
            try:
                result = delete_image(public_id)

                if result.get("result") not in ("ok", "not found"):
                    failed_deletions.append(public_id)

            except Exception:
                logger.exception(
                    "Failed to delete replaced Cloudinary image %s",
                    public_id
                )
                failed_deletions.append(public_id)

        if failed_deletions:
            return {
                "message": (
                    "Post images were updated, but some old Cloudinary "
                    "files could not be deleted."
                ),
                "failed_image_count": len(failed_deletions),
                "post": post_to_dict(post)
            }, 500

        messages = {
            "add": "Images added to post successfully.",
            "replace_selected": "Selected post images replaced successfully.",
            "replace_all": "All post images replaced successfully."
        }

        return {
            "message": messages[mode],
            "post": post_to_dict(post)
        }, 201


    @jwt_required()
    def delete(self, post_id, image_id=None):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        post = db.session.get(Post, post_id)

        if not post:
            return {"message": "Post not found."}, 404

        if image_id is not None:
            images_to_delete = [
                image for image in post.images
                if image.id == image_id
            ]

            if not images_to_delete:
                return {
                    "message": "Image not found for this post."
                }, 404
        else:
            images_to_delete = list(post.images)

            if not images_to_delete:
                return {
                    "message": "This post has no images to delete."
                }, 404

        public_ids = [
            image.public_id for image in images_to_delete
        ]

        try:
            for image in images_to_delete:
                db.session.delete(image)

            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            return {
                "message": "Unable to delete image records."
            }, 500

        failed_deletions = []

        for public_id in public_ids:
            try:
                result = delete_image(public_id)

                if result.get("result") not in ("ok", "not found"):
                    failed_deletions.append(public_id)

            except Exception:
                logger.exception(
                    "Failed to delete Cloudinary image %s",
                    public_id
                )
                failed_deletions.append(public_id)

        if failed_deletions:
            return {
                "message": (
                    "Image records deleted, but some Cloudinary files "
                    "could not be deleted."
                ),
                "failed_image_count": len(failed_deletions)
            }, 500

        return {
            "message": (
                "Post image deleted successfully."
                if image_id is not None
                else "All post images deleted successfully."
            )
        }, 200

class AdminPostsResource(Resource):
    @jwt_required()
    def get(self):
        current_user = get_current_user()

        if not current_user:
            return {"message": "User not found."}, 404

        if current_user.role != "admin":
            return {"message": "Admin access required."}, 403

        # Optionally filter by status: draft or published
        status = request.args.get("status")

        query = Post.query

        if status:
            status = status.strip().lower()

            if status not in ("draft", "published"):
                return {
                    "message": "Invalid status. Use 'draft' or 'published'."
                }, 400

            query = query.filter_by(status=status)

        posts = query.order_by(Post.created_at.desc()).all()

        return {
            "posts": [post_to_dict(post) for post in posts],
            "total": len(posts)
        }, 200
