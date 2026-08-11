from flask import Blueprint, request, jsonify
from database import get_connection
import hashlib


auth = Blueprint("auth", __name__)


# =========================================================
# SIGNUP
# =========================================================

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

    print("Fullname:", fullname)
    print("Email:", email)
    print("Phone:", phone)
    print("Password received:", bool(password))

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

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

    # Remove accidental spaces
    fullname = fullname.strip()
    email = email.strip().lower()
    phone = phone.strip()

    try:

        db = get_connection()

        if db is None:
            return jsonify({
                "success": False,
                "message": "MySQL connection failed"
            }), 500

        cursor = db.cursor()

        # -------------------------------------------------
        # CHECK EXISTING EMAIL
        # -------------------------------------------------

        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()
            db.close()

            print("EMAIL ALREADY REGISTERED:", email)

            return jsonify({
                "success": False,
                "message": "Email already registered. Please login."
            }), 409

        # -------------------------------------------------
        # HASH PASSWORD
        # -------------------------------------------------

        hashed_password = hashlib.sha256(
            password.encode()
        ).hexdigest()

        # -------------------------------------------------
        # INSERT USER
        # -------------------------------------------------

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


# =========================================================
# LOGIN
# =========================================================

@auth.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    print("================================")
    print("LOGIN DATA RECEIVED:", data)
    print("================================")

    if not data:

        return jsonify({
            "success": False,
            "message": "No login data received"
        }), 400

    email = data.get("email")
    password = data.get("password")

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not email:

        return jsonify({
            "success": False,
            "message": "Email is required"
        }), 400

    if not password:

        return jsonify({
            "success": False,
            "message": "Password is required"
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

        # -------------------------------------------------
        # FIND USER BY EMAIL
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT id, fullname, email, phone, password
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        # -------------------------------------------------
        # USER NOT FOUND
        # -------------------------------------------------

        if not user:

            cursor.close()
            db.close()

            print("LOGIN FAILED: USER NOT FOUND")

            return jsonify({
                "success": False,
                "message": "Account not found. Please create an account first."
            }), 401

        # -------------------------------------------------
        # HASH ENTERED PASSWORD
        # -------------------------------------------------

        hashed_password = hashlib.sha256(
            password.encode()
        ).hexdigest()

        # -------------------------------------------------
        # CHECK PASSWORD
        # -------------------------------------------------

        if hashed_password != user["password"]:

            cursor.close()
            db.close()

            print("LOGIN FAILED: INCORRECT PASSWORD")

            return jsonify({
                "success": False,
                "message": "Incorrect password"
            }), 401

        # -------------------------------------------------
        # LOGIN SUCCESS
        # -------------------------------------------------

        cursor.close()
        db.close()

        print("LOGIN SUCCESSFUL:", user["email"])

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