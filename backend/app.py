from flask import Flask, jsonify, request
from flask_cors import CORS

import sys
import threading
from pathlib import Path

import cv2
import numpy as np


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PROJECT_DIR = BASE_DIR.parent

AI_DIR = PROJECT_DIR / "ai"


# Add AI folder to Python path
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

# Allow frontend from another laptop on same network
CORS(app)


# ============================================================
# REGISTER AUTH ROUTES
# ============================================================

try:

    from routes.auth import auth

    app.register_blueprint(
        auth,
        url_prefix="/api"
    )

    print("Authentication routes loaded successfully.")

except Exception as e:

    print("\nERROR: Could not load authentication routes.")
    print(str(e))


# ============================================================
# AI IMPORTS
# ============================================================

try:

    from predict import (
        load_model,
        load_labels,
        create_hand_landmarker,
        predict_frame
    )

    print("\nAI prediction module loaded successfully.")


except Exception as e:

    print("\nERROR: Could not load AI prediction module.")
    print(str(e))

    load_model = None
    load_labels = None
    create_hand_landmarker = None
    predict_frame = None


# ============================================================
# GLOBAL AI OBJECTS
# ============================================================

MODEL = None

LABELS = None

LANDMARKER = None


# MediaPipe must not receive simultaneous prediction requests
AI_LOCK = threading.Lock()


# ============================================================
# TIMESTAMP CONTROL
# ============================================================

LAST_TIMESTAMP_MS = 0


# ============================================================
# LOAD AI
# ============================================================

def initialize_ai():

    global MODEL
    global LABELS
    global LANDMARKER
    global LAST_TIMESTAMP_MS

    print("\n" + "=" * 60)

    print("INITIALIZING MISSVOICE AI")

    print("=" * 60)


    try:

        # ----------------------------------------------------
        # Check prediction module
        # ----------------------------------------------------

        if load_model is None:

            raise RuntimeError(
                "predict.py could not be imported."
            )


        # ----------------------------------------------------
        # Close old landmarker
        # ----------------------------------------------------

        if LANDMARKER is not None:

            try:

                LANDMARKER.close()

            except Exception:

                pass


        # ----------------------------------------------------
        # Load trained model
        # ----------------------------------------------------

        print("\nLoading trained model...")

        MODEL = load_model()

        print(
            "Trained model loaded successfully."
        )


        # ----------------------------------------------------
        # Load labels
        # ----------------------------------------------------

        LABELS = load_labels()


        print("\nAvailable signs:")

        for index, label in enumerate(LABELS):

            print(
                f"{index}: {label}"
            )


        # ----------------------------------------------------
        # Create MediaPipe Hand Landmarker
        # ----------------------------------------------------

        print(
            "\nLoading MediaPipe Hand Landmarker..."
        )

        LANDMARKER = create_hand_landmarker()


        print(
            "MediaPipe Hand Landmarker loaded successfully."
        )


        # ----------------------------------------------------
        # Reset timestamp
        # ----------------------------------------------------

        LAST_TIMESTAMP_MS = 0


        print("\nAI initialization completed.")

        return True


    except Exception as e:

        print(
            "\nAI initialization failed:"
        )

        print(str(e))


        MODEL = None

        LABELS = None

        LANDMARKER = None


        return False


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({

        "success": True,

        "service":
            "MissVoice",

        "message":
            "MissVoice Backend Running Successfully",

        "server":
            "10.42.134.97:5000",

        "api":
            "/api"

    })


# ============================================================
# SERVER STATUS
# ============================================================

@app.route(
    "/api/status",
    methods=["GET"]
)
def status():

    return jsonify({

        "success": True,

        "backend":
            "running",

        "service":
            "MissVoice",

        "ai":
            "ready"
            if MODEL is not None
            else "not ready",

        "translation":
            "available"
            if (
                MODEL is not None
                and LABELS is not None
                and LANDMARKER is not None
            )
            else "unavailable",

        "server":
            "10.42.134.97:5000"

    })


# ============================================================
# AI STATUS
# ============================================================

@app.route(
    "/api/ai-status",
    methods=["GET"]
)
def ai_status():

    return jsonify({

        "success": True,

        "model_loaded":
            MODEL is not None,

        "labels_loaded":
            LABELS is not None,

        "landmarker_loaded":
            LANDMARKER is not None,

        "labels":
            LABELS if LABELS is not None else []

    })


# ============================================================
# SIGN LANGUAGE TRANSLATION
# ============================================================

@app.route(
    "/api/translate-sign",
    methods=["POST"]
)
def translate_sign():

    global LAST_TIMESTAMP_MS


    # --------------------------------------------------------
    # Check AI
    # --------------------------------------------------------

    if (
        MODEL is None
        or LABELS is None
        or LANDMARKER is None
    ):

        return jsonify({

            "success": False,

            "error":
                "AI model is not initialized."

        }), 503


    try:

        # ====================================================
        # CHECK FRAME
        # ====================================================

        if "frame" not in request.files:

            return jsonify({

                "success": False,

                "error":
                    "No frame received."

            }), 400


        frame_file = request.files["frame"]


        # ====================================================
        # READ IMAGE
        # ====================================================

        file_bytes = np.frombuffer(

            frame_file.read(),

            dtype=np.uint8

        )


        frame = cv2.imdecode(

            file_bytes,

            cv2.IMREAD_COLOR

        )


        if frame is None:

            return jsonify({

                "success": False,

                "error":
                    "Invalid image frame."

            }), 400


        # ====================================================
        # TIMESTAMP
        # ====================================================

        timestamp_string = request.form.get(
            "timestamp",
            "0"
        )


        try:

            timestamp_ms = int(
                timestamp_string
            )

        except ValueError:

            timestamp_ms = 0


        # ====================================================
        # MAKE TIMESTAMP MONOTONIC
        # ====================================================

        with AI_LOCK:

            if timestamp_ms <= LAST_TIMESTAMP_MS:

                timestamp_ms = (
                    LAST_TIMESTAMP_MS + 1
                )


            LAST_TIMESTAMP_MS = timestamp_ms


            # =================================================
            # PREDICT
            # =================================================

            label, confidence = predict_frame(

                frame,

                LANDMARKER,

                MODEL,

                LABELS,

                timestamp_ms

            )


        # ====================================================
        # NO SIGN DETECTED
        # ====================================================

        if label is None:

            return jsonify({

                "success": True,

                "detected": False,

                "word": "",

                "confidence":
                    round(
                        float(confidence),
                        3
                    )

            })


        # ====================================================
        # SIGN DETECTED
        # ====================================================

        return jsonify({

            "success": True,

            "detected": True,

            "word":
                str(label),

            "confidence":
                round(
                    float(confidence),
                    3
                )

        })


    except Exception as e:

        print(
            "\n========================================"
        )

        print(
            "SIGN TRANSLATION ERROR"
        )

        print(
            "========================================"
        )

        print(
            str(e)
        )


        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# RELOAD AI
# ============================================================

@app.route(
    "/api/reload-ai",
    methods=["POST"]
)
def reload_ai():

    try:

        success = initialize_ai()


        if success:

            return jsonify({

                "success": True,

                "message":
                    "AI reloaded successfully."

            })


        return jsonify({

            "success": False,

            "error":
                "AI reload failed."

        }), 500


    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# ============================================================
# NETWORK TEST
# ============================================================

@app.route(
    "/api/network-test",
    methods=["GET"]
)
def network_test():

    return jsonify({

        "success": True,

        "message":
            "Network connection to MissVoice backend is working.",

        "server_ip":
            "10.42.134.97",

        "port":
            5000

    })


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    print(
        "\n=============================================="
    )

    print(
        "        MISSVOICE BACKEND SERVER"
    )

    print(
        "=============================================="
    )

    print(
        f"Project: {PROJECT_DIR}"
    )

    print(
        f"AI folder: {AI_DIR}"
    )


    # --------------------------------------------------------
    # Initialize AI
    # --------------------------------------------------------

    ai_ready = initialize_ai()


    print(
        "\n=============================================="
    )

    print(
        "SERVER ADDRESSES"
    )

    print(
        "=============================================="
    )

    print(
        "This laptop:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print(
        "\nOther devices on same Wi-Fi:"
    )

    print(
        "http://10.42.134.97:5000"
    )


    print(
        "\nAPI:"
    )

    print(
        "http://10.42.134.97:5000/api"
    )


    print(
        "\nAI status:"
    )

    if ai_ready:

        print(
            "READY"
        )

    else:

        print(
            "NOT READY"
        )


    print(
        "\n=============================================="
    )

    print(
        "Starting Flask..."
    )

    print(
        "==============================================\n"
    )


    # --------------------------------------------------------
    # IMPORTANT:
    #
    # 0.0.0.0 allows other devices on the same network
    # to connect to this Flask server.
    # --------------------------------------------------------

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )