from flask import Flask, jsonify
from flask_cors import CORS
from routes.auth import auth


app = Flask(__name__)

CORS(app)


# Register routes
app.register_blueprint(auth, url_prefix="/api")


@app.route("/")
def home():
    return jsonify({
        "message": "MissVoice Backend Running Successfully"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )