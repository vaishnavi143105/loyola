import numpy as np
from sklearn.ensemble import RandomForestClassifier


def create_model():
    """
    Create the classifier used by MissVoice.

    Input:
        Hand landmark features

    Output:
        Sign-language class
    """

    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=20,
        random_state=42,
        class_weight="balanced"
    )

    return model


def prepare_features(landmarks):
    """
    Convert MediaPipe hand landmarks into a normalized
    feature vector.

    landmarks:
        List of 21 hand landmarks.
    """

    if landmarks is None or len(landmarks) != 21:
        return None

    points = np.array(
        [[lm.x, lm.y, lm.z] for lm in landmarks],
        dtype=np.float32
    )

    # Make wrist the origin
    points = points - points[0]

    # Normalize according to hand size
    max_distance = np.max(np.linalg.norm(points, axis=1))

    if max_distance > 0:
        points = points / max_distance

    return points.flatten()