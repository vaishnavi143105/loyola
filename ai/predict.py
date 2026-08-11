
import cv2
import joblib
import numpy as np
import mediapipe as mp

from pathlib import Path
from collections import deque, Counter

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

# Process every 5th frame
FRAME_STEP = 5

# MediaPipe settings
MIN_DETECTION_CONFIDENCE = 0.5
MIN_PRESENCE_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

MAX_NUM_HANDS = 2

# Prediction must reach this confidence
MIN_PREDICTION_CONFIDENCE = 0.70

# Number of recent predictions used for voting
SMOOTHING_WINDOW = 9

# Minimum percentage of the window that must agree
MIN_STABLE_RATIO = 0.60

# Number of consecutive stable windows required
REQUIRED_STABLE_WINDOWS = 2

# Frames to wait before accepting the same sign again
COOLDOWN_FRAMES = 20


# ============================================================
# LOAD LABELS
# ============================================================

def load_labels():

    if not LABELS_FILE.exists():

        raise FileNotFoundError(
            f"\nERROR: labels.txt not found:\n"
            f"{LABELS_FILE}"
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
            f"\nERROR: Trained model not found:\n"
            f"{MODEL_FILE}\n\n"
            "Run train.py first."
        )

    print("\nLoading trained model...")

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
            f"\nERROR: hand_landmarker.task not found:\n"
            f"{HAND_MODEL_FILE}"
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
    # Convert BGR → RGB
    # --------------------------------------------------------

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    # --------------------------------------------------------
    # Create MediaPipe image
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

    hand_landmarks = result.hand_landmarks[0]

    # --------------------------------------------------------
    # Prepare features
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
    )

    features = features.reshape(
        1,
        -1
    )

    # --------------------------------------------------------
    # Predict
    # --------------------------------------------------------

    prediction = model.predict(
        features
    )[0]

    # --------------------------------------------------------
    # Confidence
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

    if (
        prediction < 0
        or prediction >= len(labels)
    ):

        return None, confidence

    label = labels[prediction]

    # --------------------------------------------------------
    # Reject low-confidence predictions
    # --------------------------------------------------------

    if confidence < MIN_PREDICTION_CONFIDENCE:

        return None, confidence

    return label, confidence


# ============================================================
# STABLE PREDICTION
# ============================================================

class StableSignDetector:

    def __init__(self):

        self.prediction_history = deque(
            maxlen=SMOOTHING_WINDOW
        )

        self.stable_sign = None

        self.stable_count = 0

        self.last_accepted_sign = None

        self.cooldown = 0


    def update(
        self,
        label
    ):

        # ----------------------------------------------------
        # No prediction
        # ----------------------------------------------------

        if label is None:

            return None

        # ----------------------------------------------------
        # Add prediction to history
        # ----------------------------------------------------

        self.prediction_history.append(
            label
        )

        # Need enough frames before voting
        if len(
            self.prediction_history
        ) < SMOOTHING_WINDOW:

            return None

        # ----------------------------------------------------
        # Majority vote
        # ----------------------------------------------------

        counts = Counter(
            self.prediction_history
        )

        majority_label, majority_count = (
            counts.most_common(1)[0]
        )

        stable_ratio = (
            majority_count
            / len(self.prediction_history)
        )

        # ----------------------------------------------------
        # Check stability
        # ----------------------------------------------------

        if stable_ratio >= MIN_STABLE_RATIO:

            if majority_label == self.stable_sign:

                self.stable_count += 1

            else:

                self.stable_sign = (
                    majority_label
                )

                self.stable_count = 1

        else:

            self.stable_count = 0

        # ----------------------------------------------------
        # Cooldown
        # ----------------------------------------------------

        if self.cooldown > 0:

            self.cooldown -= 1

            return None

        # ----------------------------------------------------
        # Accept stable sign
        # ----------------------------------------------------

        if (
            self.stable_count
            >= REQUIRED_STABLE_WINDOWS
        ):

            # Do not repeat the same sign
            if (
                self.last_accepted_sign
                == self.stable_sign
            ):

                return None

            accepted_sign = (
                self.stable_sign
            )

            self.last_accepted_sign = (
                accepted_sign
            )

            self.cooldown = (
                COOLDOWN_FRAMES
            )

            # Clear history after accepting
            self.prediction_history.clear()

            self.stable_count = 0

            return accepted_sign

        return None


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
            f"\nERROR: Cannot open video:\n"
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

    # --------------------------------------------------------
    # Create stable detector
    # --------------------------------------------------------

    stable_detector = (
        StableSignDetector()
    )

    frame_number = 0

    detected_signs = []

    current_display = "No stable sign"

    # ========================================================
    # PROCESS VIDEO
    # ========================================================

    try:

        while True:

            success, frame = cap.read()

            if not success:

                break

            frame_number += 1

            # ------------------------------------------------
            # Process every Nth frame
            # ------------------------------------------------

            if frame_number % FRAME_STEP != 0:

                continue

            # ------------------------------------------------
            # Timestamp
            # ------------------------------------------------

            timestamp_ms = int(
                ((frame_number - 1) / fps)
                * 1000
            )

            # ------------------------------------------------
            # Predict current frame
            # ------------------------------------------------

            label, confidence = predict_frame(
                frame,
                landmarker,
                model,
                labels,
                timestamp_ms
            )

            # ------------------------------------------------
            # Update stable detector
            # ------------------------------------------------

            accepted_sign = (
                stable_detector.update(
                    label
                )
            )

            # ------------------------------------------------
            # If stable sign accepted
            # ------------------------------------------------

            if accepted_sign is not None:

                detected_signs.append(
                    accepted_sign
                )

                print(
                    f"STABLE SIGN: "
                    f"{accepted_sign}"
                )

                current_display = (
                    f"Detected: "
                    f"{accepted_sign}"
                )

            # ------------------------------------------------
            # Display current raw prediction
            # ------------------------------------------------

            if label is not None:

                raw_text = (
                    f"Raw: {label} "
                    f"({confidence * 100:.1f}%)"
                )

            else:

                raw_text = (
                    "Raw: No hand/sign"
                )

            cv2.putText(
                frame,
                raw_text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 0),
                2
            )

            # ------------------------------------------------
            # Display stable result
            # ------------------------------------------------

            cv2.putText(
                frame,
                current_display,
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 0),
                2
            )

            # ------------------------------------------------
            # Display sentence so far
            # ------------------------------------------------

            if detected_signs:

                sentence = " ".join(
                    detected_signs
                )

            else:

                sentence = "Waiting..."

            cv2.putText(
                frame,
                "Sentence: " + sentence,
                (20, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            # ------------------------------------------------
            # Show video
            # ------------------------------------------------

            cv2.imshow(
                "MissVoice - Sign Translation",
                frame
            )

            # ------------------------------------------------
            # Press Q to quit
            # ------------------------------------------------

            key = (
                cv2.waitKey(1)
                & 0xFF
            )

            if key == ord("q"):

                break

    finally:

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

        print("\nDetected signs:")

        print(
            detected_signs
        )

        sentence = " ".join(
            detected_signs
        )

        print("\nSentence:")

        print(
            sentence
        )

    else:

        print(
            "\nNo stable signs detected."
        )

    print("=" * 60)


# ============================================================
# FLASK / WEB APPLICATION FUNCTION
# ============================================================

def translate_video(video_path):

    model = load_model()

    labels = load_labels()

    cap = cv2.VideoCapture(
        str(video_path)
    )

    if not cap.isOpened():

        raise ValueError(
            f"Cannot open video: {video_path}"
        )

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    if fps <= 0:

        fps = 30

    landmarker = create_hand_landmarker()

    stable_detector = (
        StableSignDetector()
    )

    frame_number = 0

    detected_signs = []

    try:

        while True:

            success, frame = cap.read()

            if not success:

                break

            frame_number += 1

            if frame_number % FRAME_STEP != 0:

                continue

            timestamp_ms = int(
                ((frame_number - 1) / fps)
                * 1000
            )

            label, confidence = predict_frame(
                frame,
                landmarker,
                model,
                labels,
                timestamp_ms
            )

            accepted_sign = (
                stable_detector.update(
                    label
                )
            )

            if accepted_sign is not None:

                detected_signs.append(
                    accepted_sign
                )

    finally:

        cap.release()

        landmarker.close()

    sentence = " ".join(
        detected_signs
    )

    return {
        "signs": detected_signs,
        "sentence": sentence
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    video_path = input(
        "\nEnter video path: "
    ).strip()

    if not video_path:

        print(
            "\nERROR: Video path cannot be empty."
        )

    else:

        predict_video(
            video_path
        )

