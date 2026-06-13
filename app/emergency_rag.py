"""
RAG مصغّر مستقل لحالات الطوارئ فقط.

- المصدر: GradData/emergency_rag_data.json (قراءة فقط، لا يُعدَّل من التطبيق).
- المراحل: Load → TF-IDF (in-memory) → Retrieval بـ cosine similarity.
- منفصل تماماً عن RagData العام (rag.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import json
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
EMERGENCY_RAG_PATH = BASE_DIR / "GradData" / "emergency_rag_data.json"

# نصوص قصيرة نسبياً؛ n-gram ثنائي يساعد على تجميعات الأعراض
EMERGENCY_MAX_FEATURES = 6000
EMERGENCY_NGRAM = (1, 2)


@dataclass
class EmergencyRagDocument:
    doc_id: str
    text: str


class EmergencyRagIndex:
    """
    فهرس طوارئ in-memory: يحمّل مصفوفة الأنماط من JSON ويبني TF-IDF.
    """

    def __init__(self) -> None:
        self.vectorizer: TfidfVectorizer | None = None
        self.doc_matrix: np.ndarray | None = None
        self.documents: List[EmergencyRagDocument] = []

    def load_documents(self) -> None:
        """المرحلة 1: تحميل السجلات من emergency_rag_data.json."""
        self.documents = []
        if not EMERGENCY_RAG_PATH.exists():
            logger.warning("emergency_rag_data.json not found at %s", EMERGENCY_RAG_PATH)
            return
        try:
            with EMERGENCY_RAG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load emergency RAG JSON: %s", e)
            return
        if not isinstance(data, list):
            return
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            symptoms = item.get("symptoms")
            if not isinstance(symptoms, list):
                continue
            text = " ".join(str(s).strip() for s in symptoms if s and str(s).strip())
            if not text:
                continue
            self.documents.append(EmergencyRagDocument(doc_id=f"emergency_{i}", text=text))

    def build_index(self) -> None:
        """المرحلة 2: بناء مصفوفة TF-IDF."""
        if not self.documents:
            self.load_documents()
        if not self.documents:
            self.vectorizer = None
            self.doc_matrix = None
            return
        corpus = [d.text for d in self.documents]
        self.vectorizer = TfidfVectorizer(
            max_features=EMERGENCY_MAX_FEATURES,
            ngram_range=EMERGENCY_NGRAM,
        )
        self.doc_matrix = self.vectorizer.fit_transform(corpus)

    def retrieve_with_scores(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.04,
    ) -> List[Tuple[EmergencyRagDocument, float]]:
        """المرحلة 3: استرجاع أنماط الطوارئ الأقرب للاستعلام."""
        if self.vectorizer is None or self.doc_matrix is None:
            self.build_index()
        if self.vectorizer is None or self.doc_matrix is None:
            return []
        q = (query or "").strip()
        if len(q) < 2:
            return []
        q_vec = self.vectorizer.transform([q])
        sims = cosine_similarity(q_vec, self.doc_matrix)[0]
        idxs = np.argsort(sims)[::-1][:top_k]
        out: List[Tuple[EmergencyRagDocument, float]] = []
        for i in idxs:
            score = float(sims[int(i)])
            if score < min_score:
                continue
            out.append((self.documents[int(i)], score))
        return out

    def retrieve(self, query: str, top_k: int = 5) -> List[EmergencyRagDocument]:
        return [doc for doc, _ in self.retrieve_with_scores(query, top_k=top_k)]


emergency_rag_index = EmergencyRagIndex()
