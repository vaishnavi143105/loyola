
import cv2
import joblib
import numpy as np
import mediapipe as mp

from pathlib import Path
from model import prepare_features


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_FILE = BASE_DIR / "sign_classifier.pkl"
LABELS_FILE = BASE_DIR / "labels.txt"
HAND_MODEL_FILE = BASE_DIR / "hand_landmarker.task"


# ============================================================
# SETTINGS
# ============================================================

FRAME_STEP = 5

MIN_DETECTION_CONFIDENCE = 0.5
MIN_PRESENCE_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

MAX_NUM_HANDS = 2

# Only accept predictions above this confidence
PREDICTION_CONFIDENCE = 0.60


# ============================================================
# LOAD LABELS
# ============================================================

def load_labels():

    if not LABELS_FILE.exists():

        raise FileNotFoundError(
            f"labels.txt not found:\n{LABELS_FILE}"
        )

    with open(
        LABELS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        labels = [
            line.strip()
            for line in file
            if line.strip()
        ]

    return labels


# ============================================================
# LOAD TRAINED MODEL
# ============================================================

def load_model():

    if not MODEL_FILE.exists():

        raise FileNotFoundError(
            f"Trained model not found:\n{MODEL_FILE}\n\n"
            "Run train.py first."
        )

    print("Loading trained model...")

    model = joblib.load(
        MODEL_FILE
    )

    print("Model loaded successfully.")

    return model


# ============================================================
# CREATE MEDIAPIPE HAND LANDMARKER
# ============================================================

def create_hand_landmarker():

    if not HAND_MODEL_FILE.exists():

        raise FileNotFoundError(
            f"MediaPipe model not found:\n"
            f"{HAND_MODEL_FILE}\n\n"
            "Place hand_landmarker.task inside the ai folder."
        )

    base_options = mp.tasks.BaseOptions(
        model_asset_path=str(
            HAND_MODEL_FILE
        )
    )

    options = mp.tasks.vision.HandLandmarkerOptions(

        base_options=base_options,

        running_mode=(
            mp.tasks.vision.RunningMode.VIDEO
        ),

        num_hands=MAX_NUM_HANDS,

        min_hand_detection_confidence=(
            MIN_DETECTION_CONFIDENCE
        ),

        min_hand_presence_confidence=(
            MIN_PRESENCE_CONFIDENCE
        ),

        min_tracking_confidence=(
            MIN_TRACKING_CONFIDENCE
        )
    )

    landmarker = (
        mp.tasks.vision.HandLandmarker
        .create_from_options(options)
    )

    return landmarker


# ============================================================
# PREDICT ONE FRAME
# ============================================================

def predict_frame(
    frame,
    landmarker,
    model,
    labels,
    timestamp_ms
):

    # --------------------------------------------------------
    # OpenCV BGR → RGB
    # --------------------------------------------------------

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    # --------------------------------------------------------
    # MediaPipe Image
    # --------------------------------------------------------

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    # --------------------------------------------------------
    # Detect hands
    # --------------------------------------------------------

    result = landmarker.detect_for_video(
        mp_image,
        timestamp_ms
    )

    if not result.hand_landmarks:

        return None, 0.0

    # --------------------------------------------------------
    # Use first detected hand
    # --------------------------------------------------------

    hand_landmarks = (
        result.hand_landmarks[0]
    )

    # --------------------------------------------------------
    # Convert landmarks into features
    # --------------------------------------------------------

    features = prepare_features(
        hand_landmarks
    )

    if features is None:

        return None, 0.0

    # --------------------------------------------------------
    # Convert to NumPy
    # --------------------------------------------------------

    features = np.asarray(
        features,
        dtype=np.float32
    ).reshape(1, -1)

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    prediction = model.predict(
        features
    )[0]

    # --------------------------------------------------------
    # Prediction confidence
    # --------------------------------------------------------

    confidence = 0.0

    if hasattr(
        model,
        "predict_proba"
    ):

        probabilities = model.predict_proba(
            features
        )[0]

        confidence = float(
            np.max(probabilities)
        )

    # --------------------------------------------------------
    # Convert class ID → label
    # --------------------------------------------------------

    prediction = int(
        prediction
    )

    if prediction >= len(labels):

        return None, confidence

    label = labels[prediction]

    # --------------------------------------------------------
    # Ignore low-confidence prediction
    # --------------------------------------------------------

    if confidence < PREDICTION_CONFIDENCE:

        return None, confidence

    return label, confidence


# ============================================================
# PREDICT VIDEO
# ============================================================

def predict_video(video_path):

    print("\n" + "=" * 60)
    print("MISSVOICE SIGN LANGUAGE PREDICTION")
    print("=" * 60)

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    model = load_model()

    # --------------------------------------------------------
    # Load labels
    # --------------------------------------------------------

    labels = load_labels()

    print("\nAvailable signs:")

    for index, label in enumerate(labels):

        print(
            f"{index}: {label}"
        )

    # --------------------------------------------------------
    # Open video
    # --------------------------------------------------------

    cap = cv2.VideoCapture(
        str(video_path)
    )

    if not cap.isOpened():

        print(
            f"\nERROR: Could not open video:\n"
            f"{video_path}"
        )

        return

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    if fps <= 0:

        fps = 30

    # --------------------------------------------------------
    # Create MediaPipe
    # --------------------------------------------------------

    print(
        "\nLoading MediaPipe Hand Landmarker..."
    )

    landmarker = create_hand_landmarker()

    print(
        "MediaPipe Hand Landmarker loaded successfully."
    )

    frame_number = 0

    detected_signs = []

    last_prediction = None

    # ========================================================
    # PROCESS VIDEO
    # ========================================================

    while True:

        success, frame = cap.read()

        if not success:

            break

        frame_number += 1

        # ----------------------------------------------------
        # Process every Nth frame
        # ----------------------------------------------------

        if frame_number % FRAME_STEP != 0:

            continue

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        timestamp_ms = int(
            ((frame_number - 1) / fps) * 1000
        )

        # ----------------------------------------------------
        # Predict
        # ----------------------------------------------------

        label, confidence = predict_frame(
            frame,
            landmarker,
            model,
            labels,
            timestamp_ms
        )

        # ----------------------------------------------------
        # Display prediction
        # ----------------------------------------------------

        if label is not None:

            display_text = (
                f"{label} "
                f"({confidence * 100:.1f}%)"
            )

            cv2.putText(
                frame,
                display_text,
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

            # ------------------------------------------------
            # Add sign only when prediction changes
            # ------------------------------------------------

            if label != last_prediction:

                detected_signs.append(
                    label
                )

                last_prediction = label

                print(
                    f"Detected: {label} "
                    f"({confidence * 100:.1f}%)"
                )

        # ----------------------------------------------------
        # Show video
        # ----------------------------------------------------

        cv2.imshow(
            "MissVoice - Sign Translation",
            frame
        )

        # Press Q to stop
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):

            break

    # ========================================================
    # CLEANUP
    # ========================================================

    cap.release()

    cv2.destroyAllWindows()

    landmarker.close()

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print("\n" + "=" * 60)
    print("TRANSLATION RESULT")
    print("=" * 60)

    if detected_signs:

        print(
            "Detected signs:"
        )

        print(
            detected_signs
        )

        sentence = " ".join(
            detected_signs
        )

        print(
            "\nSentence:"
        )

        print(
            sentence
        )

    else:

        print(
            "No signs detected."
        )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    video_path = input(
        "\nEnter video path: "
    ).strip()

    predict_video(
        video_path
    )

