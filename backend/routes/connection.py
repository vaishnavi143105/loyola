from flask import Blueprint, request, jsonify
from database import get_connection

connections = Blueprint("connections", __name__)


# ============================================================
# SEND CONNECTION REQUEST
# ============================================================

@connections.route("/connect", methods=["POST"])
def send_connection_request():

    data = request.get_json()

    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")

    if not sender_id or not receiver_id:
        return jsonify({
            "success": False,
            "message": "Sender and receiver are required"
        }), 400

    # User cannot connect to themselves
    if int(sender_id) == int(receiver_id):
        return jsonify({
            "success": False,
            "message": "You cannot connect to yourself"
        }), 400

    try:

        db = get_connection()

        if db is None:
            return jsonify({
                "success": False,
                "message": "Database connection failed"
            }), 500

        cursor = db.cursor(dictionary=True)

        # Check receiver exists
        cursor.execute(
            "SELECT id, fullname, email FROM users WHERE id = %s",
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

        # Check existing request
        cursor.execute(
            """
            SELECT id, status
            FROM connection_requests
            WHERE sender_id = %s
            AND receiver_id = %s
            """,
            (sender_id, receiver_id)
        )

        existing = cursor.fetchone()

        if existing:

            cursor.close()
            db.close()

            if existing["status"] == "pending":
                return jsonify({
                    "success": False,
                    "message": "Connection request already sent"
                }), 409

            if existing["status"] == "accepted":
                return jsonify({
                    "success": False,
                    "message": "You are already connected"
                }), 409

        # Create request
        cursor.execute(
            """
            INSERT INTO connection_requests
            (sender_id, receiver_id, status)
            VALUES (%s, %s, 'pending')
            """,
            (sender_id, receiver_id)
        )

        db.commit()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Connection request sent successfully"
        }), 201

    except Exception as e:

        print("CONNECTION ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500


# ============================================================
# GET PENDING REQUESTS
# ============================================================

@connections.route("/connection-requests/<int:user_id>", methods=["GET"])
def get_connection_requests(user_id):

    try:

        db = get_connection()

        if db is None:
            return jsonify({
                "success": False,
                "message": "Database connection failed"
            }), 500

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
            JOIN users u
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

@connections.route(
    "/connection-requests/<int:request_id>/accept",
    methods=["POST"]
)
def accept_connection_request(request_id):

    try:

        db = get_connection()

        if db is None:
            return jsonify({
                "success": False,
                "message": "Database connection failed"
            }), 500

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM connection_requests
            WHERE id = %s
            """,
            (request_id,)
        )

        connection_request = cursor.fetchone()

        if not connection_request:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Connection request not found"
            }), 404

        if connection_request["status"] != "pending":

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Request has already been processed"
            }), 409

        # Change request status
        cursor.execute(
            """
            UPDATE connection_requests
            SET status = 'accepted'
            WHERE id = %s
            """,
            (request_id,)
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

@connections.route(
    "/connection-requests/<int:request_id>/reject",
    methods=["POST"]
)
def reject_connection_request(request_id):

    try:

        db = get_connection()

        if db is None:
            return jsonify({
                "success": False,
                "message": "Database connection failed"
            }), 500

        cursor = db.cursor()

        cursor.execute(
            """
            UPDATE connection_requests
            SET status = 'rejected'
            WHERE id = %s
            AND status = 'pending'
            """,
            (request_id,)
        )

        db.commit()

        if cursor.rowcount == 0:

            cursor.close()
            db.close()

            return jsonify({
                "success": False,
                "message": "Request not found"
            }), 404

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