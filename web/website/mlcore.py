"""Ball-In ML core — the offline, local model "socket".

Mirrors classifier.py: a single object loaded ONCE at startup as a singleton
(get_mlcore), never per request. classifier.py loads ResNet; this is where Dev A
swaps in the real basketball models (scaler.joblib, kmeans.joblib, knn.joblib).

Right now every method returns FAKE data so the server boots and the platform and
ML work can proceed in parallel. The signatures below are the contract — Dev A
fills in the bodies against the saved models without changing the signatures.

FROZEN FEATURE SCHEMA (vector order must match registration, NBA seeding and
scout target vectors — see CLAUDE.md §5):
    [height, position_encoded, PTS, REB, AST, FG%, 3PT%, usage, defensive_rating]
"""

import threading

_lock = threading.Lock()
_instance: "MLCore | None" = None

# Number of features in a standardized player vector. Frozen — see schema above.
FEATURE_DIM = 9
# Single source of truth for vector order. Everything (registration, seeding,
# scout needs) builds vectors in THIS order. Frozen — see schema above.
FEATURE_ORDER = [
    "height", "position_encoded", "PTS", "REB", "AST",
    "FG_pct", "3PT_pct", "usage", "defensive_rating",
]
assert len(FEATURE_ORDER) == FEATURE_DIM


class MLCore:
    def __init__(self) -> None:
        # STUB: nothing to load yet. Dev A loads the offline models here ONCE, e.g.:
        #   import joblib
        #   self._scaler = joblib.load("ml/scaler.joblib")
        #   self._kmeans = joblib.load("ml/kmeans.joblib")
        #   self._knn    = joblib.load("ml/knn.joblib")
        self._ready = True

    def comparables(self, vector: list[float], k: int = 5) -> list[dict]:
        """KNN comparables: the k nearest NBA reference players to a player vector.

        Returns [{"name": str, "distance": float}], nearest first.
        STUB: fixed fake names until the KNN index is loaded.
        """
        fake = ["Alex Caruso", "Gary Payton II", "Derrick White", "Marcus Smart", "Jrue Holiday"]
        return [{"name": name, "distance": round(0.1 * (i + 1), 3)} for i, name in enumerate(fake[:k])]

    def archetype(self, vector: list[float]) -> str:
        """Unsupervised archetype: classify a player vector to its nearest cluster.

        Returns the human-readable archetype label.
        STUB: fixed label until the clustering model is loaded.
        """
        return "3&D wing"

    def need_to_vector(self, need: str) -> list[float]:
        """Map a scout's free-text need (e.g. "3&D wing") to a target feature vector.

        This is the bridge that makes the fit-scorer symmetric: a text need becomes
        a vector that fit_score can compare against any player vector.
        STUB: returns a neutral zero vector until the local archetype dictionary
        (tag -> target vector, with optional fuzzy tag match) is loaded by Dev A.
        """
        return [0.0] * FEATURE_DIM

    def fit_score(self, need: list[float], vector: list[float]) -> float:
        """Symmetric fit-scorer: how well a player vector matches a target need vector.

        Returns a score in [0, 1] (higher = better fit). The same function ranks
        players-for-a-need and needs-for-a-player — one model, two directions.
        STUB: fixed fake score until the weighted-distance scorer is wired up.
        """
        return 0.87


def get_mlcore() -> MLCore:
    """Return the singleton MLCore, creating it on first call."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = MLCore()
    return _instance
