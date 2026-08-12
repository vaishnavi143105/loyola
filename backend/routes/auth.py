from flask import Blueprint, request, jsonify
from database import get_connection
import hashlib


auth = Blueprint("auth", __name__)


# ============================================================
# HELPER - HASH PASSWORD
# ============================================================

def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


# ============================================================
# SIGNUP
# ============================================================

@auth.route("/signup", methods=["POST"])
def signup():

    data = request.get_json()

    print("================================")
    print("DATA RECEIVED:", data)
    print("================================")

    if not data:
        return jsonify({
            "success": False,
            "message": "No data received from frontend"
        }), 400

    fullname = data.get("fullname")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")

    if not fullname:
        return jsonify({
            "success": False,
            "message": "Full name is missing"
        }), 400

    if not email:
        return jsonify({
            "success": False,
            "message": "Email is missing"
        }), 400

    if not phone:
        return jsonify({
            "success": False,
            "message": "Phone is missing"
        }), 400

    if not password:
        return jsonify({
            "success": False,
            "message": "Password is missing"
        }), 400

    email = email.strip().lower()

    try:

        db = get_connection()

        if db is None:
            return jsonify({
                "success": False,
                "message": "MySQL connection failed"
            }), 500

        cursor = db.cursor()

        # ----------------------------------------------------
        # Check existing email
        # ----------------------------------------------------

        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Email already registered"
            }), 409

        # ----------------------------------------------------
        # Hash password
        # ----------------------------------------------------

        hashed_password = hash_password(password)

        # ----------------------------------------------------
        # Insert user
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO users
            (fullname, email, phone, password)
            VALUES (%s, %s, %s, %s)
            """,
            (
                fullname,
                email,
                phone,
                hashed_password
            )
        )

        db.commit()

        cursor.close()
        db.close()

        print("USER CREATED SUCCESSFULLY")

        return jsonify({
            "success": True,
            "message": "Account created successfully"
        }), 201

    except Exception as e:

        print("DATABASE ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500


# ============================================================
# LOGIN
# ============================================================

@auth.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "No data received"
        }), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    email = email.strip().lower()

    try:

        db = get_connection()

        if db is None:
            return jsonify({
                "success": False,
                "message": "MySQL connection failed"
            }), 500

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                fullname,
                email,
                phone,
                password
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        # ----------------------------------------------------
        # Account doesn't exist
        # ----------------------------------------------------

        if not user:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Account not found. Please create an account first."
            }), 404

        # ----------------------------------------------------
        # Check password
        # ----------------------------------------------------

        hashed_password = hash_password(password)

        if hashed_password != user["password"]:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Incorrect password."
            }), 401

        # ----------------------------------------------------
        # Login successful
        # ----------------------------------------------------

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "fullname": user["fullname"],
                "email": user["email"],
                "phone": user["phone"]
            }
        }), 200

    except Exception as e:

        print("LOGIN DATABASE ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500


# ============================================================
# SEARCH USER
# ============================================================

@auth.route("/search-user", methods=["GET"])
def search_user():

    username = request.args.get("username", "").strip()

    current_user_id = request.args.get("current_user_id")

    if not username:
        return jsonify({
            "success": False,
            "message": "Username is required"
        }), 400

    if not current_user_id:
        return jsonify({
            "success": False,
            "message": "Current user ID is required"
        }), 400

    try:

        db = get_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, fullname, email
            FROM users
            WHERE fullname LIKE %s
            AND id != %s
            LIMIT 10
            """,
            (
                "%" + username + "%",
                current_user_id
            )
        )

        users = cursor.fetchall()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "users": users
        }), 200

    except Exception as e:

        print("SEARCH ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500


# ============================================================
# SEND CONNECTION REQUEST
# ============================================================

@auth.route("/connect", methods=["POST"])
def connect():

    data = request.get_json()

    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")

    if not sender_id or not receiver_id:

        return jsonify({
            "success": False,
            "message": "Sender and receiver are required"
        }), 400

    if str(sender_id) == str(receiver_id):

        return jsonify({
            "success": False,
            "message": "You cannot connect with yourself"
        }), 400

    try:

        db = get_connection()
        cursor = db.cursor(dictionary=True)

        # ----------------------------------------------------
        # Check receiver exists
        # ----------------------------------------------------

        cursor.execute(
            "SELECT id, fullname FROM users WHERE id = %s",
            (receiver_id,)
        )

        receiver = cursor.fetchone()

        if not receiver:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404

        # ----------------------------------------------------
        # Check existing accepted connection
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM connections
            WHERE
            (user1_id = %s AND user2_id = %s)
            OR
            (user1_id = %s AND user2_id = %s)
            """,
            (
                sender_id,
                receiver_id,
                receiver_id,
                sender_id
            )
        )

        connection = cursor.fetchone()

        if connection:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "You are already connected with this user"
            }), 409

        # ----------------------------------------------------
        # Check pending request
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id, status
            FROM connection_requests
            WHERE
            sender_id = %s
            AND receiver_id = %s
            """,
            (
                sender_id,
                receiver_id
            )
        )

        existing_request = cursor.fetchone()

        if existing_request:

            cursor.close()
            db.close()

            if existing_request["status"] == "pending":

                return jsonify({
                    "success": False,
                    "message": "Connection request already sent"
                }), 409

            if existing_request["status"] == "rejected":

                # Allow sending again
                db = get_connection()
                cursor = db.cursor()

                cursor.execute(
                    """
                    UPDATE connection_requests
                    SET status = 'pending'
                    WHERE id = %s
                    """,
                    (existing_request["id"],)
                )

                db.commit()

                cursor.close()
                db.close()

                return jsonify({
                    "success": True,
                    "message": "Connection request sent again"
                }), 200

        # ----------------------------------------------------
        # Create request
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO connection_requests
            (sender_id, receiver_id, status)
            VALUES (%s, %s, 'pending')
            """,
            (
                sender_id,
                receiver_id
            )
        )

        db.commit()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Connection request sent"
        }), 201

    except Exception as e:

        print("CONNECT ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500


# ============================================================
# GET PENDING CONNECTION REQUESTS
# ============================================================

@auth.route("/connection-requests/<int:user_id>", methods=["GET"])
def get_connection_requests(user_id):

    try:

        db = get_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                cr.id,
                cr.sender_id,
                cr.receiver_id,
                cr.status,
                cr.created_at,
                u.fullname,
                u.email
            FROM connection_requests cr

            INNER JOIN users u
            ON cr.sender_id = u.id

            WHERE cr.receiver_id = %s
            AND cr.status = 'pending'

            ORDER BY cr.created_at DESC
            """,
            (user_id,)
        )

        requests = cursor.fetchall()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "requests": requests
        }), 200

    except Exception as e:

        print("REQUEST ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500


# ============================================================
# ACCEPT CONNECTION REQUEST
# ============================================================

@auth.route(
    "/connection-request/<int:request_id>/accept",
    methods=["POST"]
)
def accept_connection(request_id):

    data = request.get_json() or {}

    receiver_id = data.get("user_id")

    if not receiver_id:

        return jsonify({
            "success": False,
            "message": "User ID is required"
        }), 400

    try:

        db = get_connection()
        cursor = db.cursor(dictionary=True)

        # ----------------------------------------------------
        # Find pending request
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                sender_id,
                receiver_id,
                status
            FROM connection_requests
            WHERE id = %s
            """,
            (request_id,)
        )

        request_data = cursor.fetchone()

        if not request_data:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Connection request not found"
            }), 404

        # ----------------------------------------------------
        # Security check
        # ----------------------------------------------------

        if str(request_data["receiver_id"]) != str(receiver_id):

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "You cannot accept this request"
            }), 403

        if request_data["status"] != "pending":

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Request is no longer pending"
            }), 409

        sender_id = request_data["sender_id"]

        # ----------------------------------------------------
        # Update request
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE connection_requests
            SET status = 'accepted'
            WHERE id = %s
            """,
            (request_id,)
        )

        # ----------------------------------------------------
        # Store accepted connection
        # ----------------------------------------------------

        user1 = min(
            int(sender_id),
            int(receiver_id)
        )

        user2 = max(
            int(sender_id),
            int(receiver_id)
        )

        cursor.execute(
            """
            INSERT IGNORE INTO connections
            (user1_id, user2_id)
            VALUES (%s, %s)
            """,
            (
                user1,
                user2
            )
        )

        db.commit()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Connection accepted"
        }), 200

    except Exception as e:

        print("ACCEPT ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500


# ============================================================
# REJECT CONNECTION REQUEST
# ============================================================

@auth.route(
    "/connection-request/<int:request_id>/reject",
    methods=["POST"]
)
def reject_connection(request_id):

    data = request.get_json() or {}

    user_id = data.get("user_id")

    if not user_id:

        return jsonify({
            "success": False,
            "message": "User ID is required"
        }), 400

    try:

        db = get_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT receiver_id, status
            FROM connection_requests
            WHERE id = %s
            """,
            (request_id,)
        )

        request_data = cursor.fetchone()

        if not request_data:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Request not found"
            }), 404

        if str(request_data["receiver_id"]) != str(user_id):

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Unauthorized"
            }), 403

        cursor.execute(
            """
            UPDATE connection_requests
            SET status = 'rejected'
            WHERE id = %s
            """,
            (request_id,)
        )

        db.commit()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Connection request rejected"
        }), 200

    except Exception as e:

        print("REJECT ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500


# ============================================================
# GET CONNECTED USERS
# ============================================================

@auth.route(
    "/connected-users/<int:user_id>",
    methods=["GET"]
)
def get_connected_users(user_id):

    try:

        db = get_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                u.id,
                u.fullname,
                u.email

            FROM connections c

            INNER JOIN users u
            ON
            (
                u.id = c.user1_id
                AND c.user2_id = %s
            )
            OR
            (
                u.id = c.user2_id
                AND c.user1_id = %s
            )

            ORDER BY u.fullname
            """,
            (
                user_id,
                user_id
            )
        )

        users = cursor.fetchall()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "users": users
        }), 200

    except Exception as e:

        print("CONNECTED USERS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500