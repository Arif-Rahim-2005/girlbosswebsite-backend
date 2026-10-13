from flask_restful import Resource, reqparse
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User
from datetime import timedelta
from datetime import datetime
from sqlalchemy.exc import IntegrityError



class LogInResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument("email", required=True, help="email is required")
    parser.add_argument("password", required=True, help="password is required")

    def post(self):
        data = self.parser.parse_args()

        user = User.query.filter_by(email=data["email"]).first()

        if user is None:
            return {"message": "invalid email or password. If you don't have an account, please signup"}, 403

        # validate password
        if check_password_hash(user.password_hash.decode('utf-8') if isinstance(user.password_hash, bytes) else user.password_hash, data["password"]):

            # then generate access token
            access_token = create_access_token(
                identity=str(user.id),
                expires_delta=timedelta(hours=24),
            )

            return {
                "message": "Logged in successfully",
                "access_token": access_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            }, 200
        else:
            return {"message": "invalid email or password"}, 403


class SignupResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument("username", type=str, required=True, help="Username is required")
    parser.add_argument("email", type=str, required=True, help="Email is required")
    parser.add_argument("password", type=str, required=True, help="Password is required")

    def post(self):
        data = SignupResource.parser.parse_args()
        username = data["username"]
        email = data["email"]
        password = data["password"]

        # ✅ Optional: check if username or email exists

        if User.query.filter_by(email=email).first():
            return {"message": "Email already registered"}, 400

        try:
            hashed_password = generate_password_hash(password).decode('utf-8')

            new_user = User(
                username=username,
                email=email,
                password_hash=hashed_password,
                role="user",  # Default role
                created_at=datetime.utcnow(),
            )
                        # generate access Token
            db.session.add(new_user)
            db.session.commit()

            access_token = create_access_token(
                identity=str(new_user.id),
                expires_delta=timedelta(hours=24),
            )

            return {
                "message": "Account created successfully",
                "access_token": access_token,
                "user": {
                    "id": new_user.id,
                    "username": new_user.username,
                    "email": new_user.email,
                    "role": new_user.role,
                },
            }, 201

        except IntegrityError as e:
            db.session.rollback()
            return {"message": "User already exists", "error": str(e)}, 400

        except Exception as e:
            db.session.rollback()
            import traceback
            print("⚠️ ERROR IN SIGNUP ⚠️")
            traceback.print_exc()
            return {"message": "Error", "error": str(e)}, 500



class UserResource(Resource):
    parser = reqparse.RequestParser()
    parser.add_argument("username", type=str)
    parser.add_argument("email", type=str)
    parser.add_argument("role", type=str)


    @jwt_required()
    def get(self, user_id=None):
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        if not current_user:
            return {"message": "Invalid user"}, 404

        if current_user.role != "admin":
            return {"message": "Access denied: You are not authorized to view this resource"}, 403

        if user_id:
            user = User.query.get(user_id)

            if not user:
                return {"message": "User not found"}, 404

            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role
            }, 200

        # Get all users — admin only
        if current_user.role != "admin":
            return {
                "Access denied": "You are not authorized to view all users"
            }, 403

        users = User.query.all()

        return [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role
            }
            for u in users
        ], 200
    @jwt_required()
    def patch(self, user_id):
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        if not current_user:
            return {"message": "Invalid user"}, 404

        user = User.query.get(user_id)
        if not user:
            return {"message": "User not found"}, 404

        data = self.parser.parse_args()

        # Normal users can only update *their own* username or email
        if current_user.role != "admin" and current_user.id != user.id:
            return {"message": "You are not authorized to update this user"}, 403

        if data["username"]:
            user.username = data["username"]
        if data["email"]:
            user.email = data["email"]

        # Only admins can update roles
        if data["role"]:
            if current_user.role != "admin":
                return {"message": "Only admins can change roles"}, 403

            if data["role"] not in ["user", "admin"]:
                return {"message": "Invalid role"}, 400

            user.role = data["role"]

        db.session.commit()

        return {
            "message": "User updated successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
        }, 200

    @jwt_required()
    def delete(self, user_id):
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        if not current_user:
            return {"message": "Invalid user"}, 404

        user = User.query.get(user_id)
        if not user:
            return {"message": "User not found"}, 404

        # Allow self-deletion OR admin deletion
        if current_user.role != "admin" and current_user.id != user.id:
            return {"message": "You are not authorized to delete this user-account"}, 403

        db.session.delete(user)
        db.session.commit()

        return {"message": "User-account deleted successfully"}, 200

class AdminResource(Resource):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return {"message": "User not found"}, 404

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }, 200