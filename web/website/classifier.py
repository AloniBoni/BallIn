import threading

import torch
import torch.nn.functional as F
from torchvision import models
from PIL import Image

_lock = threading.Lock()
_instance: "Classifier | None" = None


class Classifier:
    def __init__(self) -> None:
        weights = models.ResNet18_Weights.DEFAULT
        self._model = models.resnet18(weights=weights)
        self._model.eval()
        self._categories: list[str] = weights.meta["categories"]
        self._preprocess = weights.transforms()

    def predict(self, image: Image.Image) -> list[dict]:
        """Return top-3 ImageNet predictions as [{"name": str, "score": float}]."""
        tensor = self._preprocess(image).unsqueeze(0)
        with torch.no_grad():
            logits = self._model(tensor)
        probs = F.softmax(logits[0], dim=0)
        top = torch.topk(probs, 3)
        # Emit the raw softmax probabilities without rounding. Each top-k value is
        # strictly > 0, and the top-3 of a full 1000-class softmax always sum to
        # strictly < 1.0 — so the (0, 1] per-score and [0, 1] sum contracts in
        # interface.md hold exactly. Rounding risked flattening a tiny 3rd score to
        # 0.0 (violating score > 0).
        return [
            {"name": self._categories[idx.item()], "score": float(score.item())}
            for score, idx in zip(top.values, top.indices)
        ]


def get_classifier() -> Classifier:
    """Return the singleton Classifier, creating it on first call."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = Classifier()
    return _instance
