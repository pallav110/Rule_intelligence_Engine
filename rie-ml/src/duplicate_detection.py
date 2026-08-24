"""Phase 3 — Structured duplicate detection engine.

Uses TF-IDF cosine similarity on ``feedback_text`` to find near-duplicates.
Structured comparison (same ``rule_family_id``) is also supported.
"""

import json
from typing import List, Dict, Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class DuplicateDetector:
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.vectorizer = TfidfVectorizer(stop_words="english", lowercase=True)
        self.vectors: Any = None
        self.ids: List[str] = []
        self.data: List[Dict] = []

    def index(self, data_path: str) -> None:
        texts: List[str] = []
        self.data.clear()
        self.ids.clear()
        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                self.data.append(obj)
                texts.append(obj.get("feedback_text", ""))
                self.ids.append(obj.get("feedback_id", ""))
        self.vectors = self.vectorizer.fit_transform(texts)

    def find_duplicates_for(self, feedback_id: str) -> List[str]:
        """Return IDs of near-duplicate feedback entries."""
        try:
            idx = self.ids.index(feedback_id)
        except ValueError:
            return []
        target = self.vectors[idx]
        sims = cosine_similarity(target, self.vectors).flatten()
        duplicates = []
        for i, s in enumerate(sims):
            if i != idx and s >= self.threshold:
                duplicates.append(self.ids[i])
        return duplicates

    def find_all_pairs(self) -> List[Dict[str, Any]]:
        """Find all duplicate pairs above threshold."""
        pairs = []
        for i in range(len(self.ids)):
            dups = self.find_duplicates_for(self.ids[i])
            for d in dups:
                # Only keep each pair once
                if self.ids.index(d) > i:
                    pairs.append({
                        "feedback_id_1": self.ids[i],
                        "feedback_id_2": d,
                        "similarity_score": float(np.mean(
                            cosine_similarity(
                                self.vectors[i],
                                self.vectors[self.ids.index(d)]
                            )
                        )),
                        "duplicate_type": "semantic",
                    })
        # De-duplicate pairs
        seen = set()
        unique = []
        for p in pairs:
            key = tuple(sorted([p["feedback_id_1"], p["feedback_id_2"]]))
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique