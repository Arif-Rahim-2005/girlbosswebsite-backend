import cloudinary
import cloudinary.uploader


def upload_image(image_file, folder="girlbosswebsite"):
    """Upload an image to Cloudinary and return its URL and public ID."""

    config = cloudinary.config()

    print("Cloudinary API key loaded:", bool(config.api_key))
    print("Cloudinary cloud name loaded:", bool(config.cloud_name))
    print("Cloudinary API secret loaded:", bool(config.api_secret))

    result = cloudinary.uploader.upload(
        image_file,
        folder=folder,
        resource_type="image"
    )

    return {
        "image_url": result["secure_url"],
        "public_id": result["public_id"]
    }


def delete_image(public_id):
    """Delete an image from Cloudinary using its public ID."""

    return cloudinary.uploader.destroy(
        public_id,
        resource_type="image"
    )
