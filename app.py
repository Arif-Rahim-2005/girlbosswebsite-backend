import os
import cloudinary
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_restful import Api
from models import db
from datetime import timedelta
from resources.users import SignupResource, LogInResource, UserResource, AdminResource
from resources.product import ProductsResource, ProductResource, ProductImagesResource
from resources.posts import PostResource, PostsResource, PostImagesResource, AdminPostsResource


load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

app = Flask(__name__)

# -------------------------
# Configuration
# -------------------------

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)

# -------------------------
# Extensions
# -------------------------

# db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
api = Api(app)

db.init_app(app)
migrate.init_app(app, db)
jwt.init_app(app)

CORS(app)

# -------------------------
# Routes
# -------------------------

@app.route("/")
def home():
    return jsonify({
        "message": "Welcome to the Girlboss Website Backend API! This is the home route"
    })


api.add_resource(SignupResource, "/signup")
api.add_resource(LogInResource, "/login")
api.add_resource(UserResource, "/users", "/users/<int:user_id>")
api.add_resource(AdminResource, "/me")

api.add_resource(ProductsResource, "/products")
api.add_resource(ProductResource, "/products/<int:product_id>")
api.add_resource(ProductImagesResource, "/products/<int:product_id>/images", "/products/<int:product_id>/images/<int:image_id>")

api.add_resource(PostsResource, "/posts")
api.add_resource(PostResource, "/posts/<int:post_id>")
api.add_resource(
    PostImagesResource,
    "/posts/<int:post_id>/images",
    "/posts/<int:post_id>/images/<int:image_id>"
)
api.add_resource(AdminPostsResource, "/posts/manage")

if __name__ == "__main__":
    app.run(debug=True)