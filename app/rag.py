from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Protocol, Sequence, Tuple, cast

import numpy as np

logger = logging.getLogger(__name__)

# ── مسارات المشروع (بدون تغيير) ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
RAG_DIR = BASE_DIR / "GradData" / "RagData"

# كاش فهرس الراج على القرص (يُعاد البناء عند تغيّر ملفات RagData أو اسم الموديل)
RAG_INDEX_CACHE_DIR = BASE_DIR / ".rag_index_cache"
RAG_INDEX_CACHE_VERSION = 1

# ── موديل الجمل متعدد اللغات — مناسب للعربية والاسترجاع الدلالي المحلي ───────
# يمكن استبداله بموديل عربي متخصص لاحقاً دون تغيير بقية الـ pipeline.
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# ── استرجاع دلالي ────────────────────────────────────────────────────────────
DEFAULT_MIN_SIMILARITY = 0.22
DEFAULT_RETRIEVAL_TOP_POOL = 40

# ── تقسيم دلالي (جمل متجاورة متشابهة) ───────────────────────────────────────
SEMANTIC_MERGE_THRESHOLD = 0.68
MAX_CHUNK_CHARS = 1100
MIN_CHUNK_CHARS = 80
SEMANTIC_OVERLAP_SENTENCES = 1

# ── إعادة ترتيب بسيطة (أوزان تجريبية قابلة للضبط) ───────────────────────────
RERANK_WEIGHT_SEMANTIC = 0.62
RERANK_WEIGHT_SYMPTOM_OVERLAP = 0.14
RERANK_WEIGHT_TOKEN_JACCARD = 0.12
RERANK_WEIGHT_DEPARTMENT = 0.08
RERANK_WEIGHT_CRITICAL = 0.04
DEPARTMENT_MATCH_BONUS = 0.12

# عبارات طبية حرجة ترفع الصلة عند تطابقها
CRITICAL_MEDICAL_PHRASES: tuple[str, ...] = (
    "ألم صدر",
    "ضيق تنفس",
    "صعوبة التنفس",
    "فقدان وعي",
    "إغماء",
    "نزيف",
    "حمى شديدة",
    "طوارئ",
    "سكتة",
    "جلطة",
)

# ── مرادفات / أسماء بديلة للأعراض الشائعة (قابلة للتوسعة) ───────────────────
# المفتاح: عبارة مرجعية بعد التطبيع؛ القيم: مرادفات تُضاف عند توسيع الاستعلام.
SYMPTOM_SYNONYM_GROUPS: dict[str, tuple[str, ...]] = {
    "ضيق تنفس": ("صعوبة التنفس", "نهجان", "اختناق", "ضيق في النفس"),
    "صعوبة التنفس": ("ضيق تنفس", "نهجان", "اختناق"),
    "ألم صدر": ("وجع صدر", "الم الصدر", "وجع في الصدر"),
    "وجع صدر": ("ألم صدر", "ألم في الصدر"),
    "إغماء": ("فقدان وعي", "غشي", "دوخة شديدة"),
    "فقدان وعي": ("إغماء", "غيبوبة"),
    "غثيان": ("قيء", "استفراغ", "الغثيان"),
    "دوخة": ("دوار", "دوار الرأس"),
    "إسهال": ("اسهال", "ليونة البراز"),
}

# بناء فهرس عكسي سريع: أي مرادف → المفتاح المرجعي
_SYN_CANONICAL: dict[str, str] = {}
for _canon, _alts in SYMPTOM_SYNONYM_GROUPS.items():
    _SYN_CANONICAL[_canon] = _canon
    for _a in _alts:
        _SYN_CANONICAL[_a] = _canon


def clear_rag_disk_cache() -> None:
    """حذف كاش الفهرس على القرص (إجبار إعادة البناء في التشغيل التالي)."""
    if RAG_INDEX_CACHE_DIR.is_dir():
        shutil.rmtree(RAG_INDEX_CACHE_DIR, ignore_errors=True)
        logger.info("RAG: removed disk cache directory %s", RAG_INDEX_CACHE_DIR)


def rag_data_fingerprint(rag_dir: Path = RAG_DIR) -> str:
    """
    بصمة محتوى مصدر RagData: كل ملف json (الاسم + الحجم + وقت التعديل).
    أي تغيير/إضافة/حذف يغيّر البصمة دون قراءة محتوى الملفات.
    """
    if not rag_dir.is_dir():
        return hashlib.sha256(b"<no_rag_dir>").hexdigest()
    lines: list[str] = []
    for p in sorted(rag_dir.glob("*.json")):
        try:
            st = p.stat()
            lines.append(f"{p.name}\t{st.st_size}\t{st.st_mtime_ns}")
        except OSError:
            lines.append(f"{p.name}\t!\t!")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def normalize_arabic_for_embedding(text: str) -> str:
    """
    تطبيع عربي قوي قبل التضمين والاستعلام: ألف، تطويل، تشكيل، همزات، ياء/ألف مقصورة.
    """
    if not text:
        return ""
    s = text.strip()
    # إزالة التطويل
    s = s.replace("\u0640", "")
    # إزالة التشكيل (Harakat)
    s = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]", "", s)
    # توحيد الألف وأشكالها
    for a in ("\u0622", "\u0623", "\u0625"):
        s = s.replace(a, "ا")
    s = s.replace("\u0671", "ا")
    # همزة على الألف → ألف
    s = re.sub(r"أ|إ|آ", "ا", s)
    # توحيد ياء / ألف مقصورة في نهاية الكلمات الشائعة
    s = re.sub(r"ى\b", "ي", s)
    s = s.replace("ى", "ي")
    # همزة الوصل والهمزات المتنوعة
    s = s.replace("ؤ", "و").replace("ئ", "ي")
    # إزالة علامات زائدة مع الحفاظ على فواصل الجمل
    s = re.sub(r"[^\w\s\u0600-\u06FF.,؛؟:!٫٬\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def expand_query_synonyms(normalized_query: str) -> str:
    """
    توسيع الاستعلام بمرادفات طبية معروفة (للاستخدام في التضمين فقط).
    لا يكرر نفس العبارة إذا وُجدت مسبقاً.
    """
    if not normalized_query:
        return ""
    extra: list[str] = []
    seen: set[str] = set()
    for canon, alts in SYMPTOM_SYNONYM_GROUPS.items():
        if canon in normalized_query or any(a in normalized_query for a in alts):
            key = _SYN_CANONICAL.get(canon, canon)
            if key in seen:
                continue
            seen.add(key)
            bag = (canon,) + alts
            for phrase in bag:
                if phrase not in normalized_query and phrase not in seen:
                    extra.append(phrase)
                    seen.add(phrase)
    if not extra:
        return normalized_query
    return normalized_query + " " + " ".join(extra[:24])


# ── تطبيع أسماء الأقسام الفوضوية في ملفات RagData إلى الأسماء الرسمية ────────
# الملفات تحتوي تسميات متعددة (مسافات زائدة، أخطاء، صيغ بديلة) لنفس القسم.
# هذه الخريطة تربطها بالتسمية الموحدة المستخدمة في النظام.
_DEPT_ALIAS_MAP: dict[str, str] = {
    "قسم الباطنية": "أمراض الجهاز الهضمي",
    "الطب الباطني": "أمراض الجهاز الهضمي",
    "الباطنية": "أمراض الجهاز الهضمي",
    "الطب العام": "أمراض الجهاز الهضمي",

    "الجلدية": "الأمراض الجلدية",
    "جلدية": "الأمراض الجلدية",
    "الحساسية والمناعة": "الأمراض الجلدية",

    "الأعصاب": "طب الأعصاب",
    "الاعصاب": "طب الأعصاب",
    "جراحة الأعصاب": "طب الأعصاب",

    "العظام": "طب العظام",
    "جراحة العظام": "طب العظام",

    "المسالك البولية": "جراحة المسالك البولية",
    "أمراض الكلى": "جراحة المسالك البولية",

    "التوليد وأمراض النساء": "النسائية والتوليد",
    "أمراض النساء والتوليد": "النسائية والتوليد",
    "طب النساء والتوليد": "النسائية والتوليد",
    "االتوليد وامراض النساء": "النسائية والتوليد",

    "الأطفال": "طب الأطفال",
    "طب الاطفال": "طب الأطفال",
    "جراحة الأطفال": "طب الأطفال",
    "طب حديثي الولادة": "طب الأطفال",

    "طب الفم": "طب الأسنان",
    "طب الاسنان": "طب الأسنان",
    "جراحة الوجه والفكين": "طب الأسنان",

    "أمراض القلب والأوعية الدموية": "أمراض القلب",
    "جراحة الأوعية الدموية": "أمراض القلب",

    "جراحة التجميل": "الأمراض الجلدية",
    "جراحة الصدر": "أمراض الصدر",
    "جراحة الجهاز الهضمي": "أمراض الجهاز الهضمي",
}


def normalize_department_name(raw: str) -> str:
    """تطبيع اسم القسم من ملف JSON إلى الاسم الرسمي الموحّد."""
    cleaned = raw.strip()
    if not cleaned:
        return ""
    mapped = _DEPT_ALIAS_MAP.get(cleaned)
    if mapped:
        return mapped
    return cleaned


def _format_list_section(title: str, items: Sequence[str]) -> str:
    if not items:
        return ""
    lines = [f"{title}:"]
    for it in items:
        it = str(it).strip()
        if it:
            lines.append(f"  - {it}")
    return "\n".join(lines)


def build_structured_medical_text(data: dict[str, Any]) -> str:
    """
    يبني نصاً طبياً منظماً مع الحفاظ على دلالة الحقول (بدلاً من join عشوائي).
    """
    blocks: list[str] = []

    disease = str(data.get("disease", "") or "").strip()
    if disease:
        blocks.append(f"disease:\n{disease}")

    dept = str(data.get("department", "") or "").strip()
    if dept:
        blocks.append(f"department:\n{dept}")

    definition = str(data.get("definition", "") or "").strip()
    if definition:
        blocks.append(f"definition:\n{definition}")

    symptoms_raw = data.get("symptoms")
    sym_lines: list[str] = ["symptoms:"]
    if isinstance(symptoms_raw, dict):
        for group_name, values in symptoms_raw.items():
            gname = str(group_name).strip()
            sym_lines.append(f"  symptom_group: {gname}")
            if isinstance(values, list):
                for v in values:
                    v = str(v).strip()
                    if v:
                        sym_lines.append(f"    - {v}")
            elif values is not None:
                sym_lines.append(f"    - {values}")
    elif isinstance(symptoms_raw, list):
        for v in symptoms_raw:
            v = str(v).strip()
            if v:
                sym_lines.append(f"  - {v}")
    elif symptoms_raw:
        sym_lines.append(f"  - {symptoms_raw}")
    if len(sym_lines) > 1:
        blocks.append("\n".join(sym_lines))

    causes = data.get("Causes", data.get("causes", []))
    cause_items = _as_str_list(causes)
    if cause_items:
        blocks.append(_format_list_section("causes", cause_items))

    rf = _as_str_list(data.get("risk_factors"))
    if rf:
        blocks.append(_format_list_section("risk_factors", rf))

    prev = _as_str_list(data.get("prevention"))
    if prev:
        blocks.append(_format_list_section("prevention", prev))

    comp = data.get("complications")
    if isinstance(comp, str) and comp.strip():
        blocks.append(f"complications:\n{comp.strip()}")
    else:
        cl = _as_str_list(comp)
        if cl:
            blocks.append(_format_list_section("complications", cl))

    diag = _as_str_list(data.get("diagnosis"))
    if diag:
        blocks.append(_format_list_section("diagnosis", diag))

    treat = _as_str_list(data.get("treatment"))
    if treat:
        blocks.append(_format_list_section("treatment", treat))

    full = "\n\n".join(blocks)
    full = re.sub(r"\s+\n", "\n", full)
    full = re.sub(r"\n{3,}", "\n\n", full)
    return re.sub(r"[ \t]{2,}", " ", full).strip()


def _as_str_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        return [val.strip()] if val.strip() else []
    return [str(val).strip()] if str(val).strip() else []


def split_arabic_sentences(text: str) -> list[str]:
    """تقسيم تقريبي إلى جمل (عربي + علامات شائعة)."""
    if not text.strip():
        return []
    parts = re.split(r"(?<=[\.\!\?\؟؛])\s+", text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    if not out:
        return [text.strip()]
    return out


def _cosine_sim_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a: (n, d), b: (m, d)"""
    a_n = np.linalg.norm(a, axis=1, keepdims=True) + 1e-12
    b_n = np.linalg.norm(b, axis=1, keepdims=True) + 1e-12
    return (a @ b.T) / (a_n * b_n.T)


class _Encoder(Protocol):
    def encode(
        self,
        sentences: Sequence[str],
        *,
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = True,
    ) -> np.ndarray: ...


def semantic_merge_sentences(
    sentences: list[str],
    sentence_embeddings: np.ndarray,
    merge_threshold: float = SEMANTIC_MERGE_THRESHOLD,
    max_chars: int = MAX_CHUNK_CHARS,
    min_chars: int = MIN_CHUNK_CHARS,
    overlap_sentences: int = SEMANTIC_OVERLAP_SENTENCES,
) -> list[str]:
    """
    يدمج الجمل المتجاورة ذات التشابه الدلالي العالي في مقطع واحد، مع حدود طول.
    """
    if not sentences:
        return []
    if len(sentences) == 1:
        return [sentences[0].strip()]
    total_len = sum(len(s) for s in sentences)
    if total_len <= min_chars * 2:
        return [" ".join(sentences).strip()]

    chunks: list[str] = []
    current: list[str] = [sentences[0]]
    for i in range(1, len(sentences)):
        prev_emb = sentence_embeddings[i - 1 : i]
        curr_emb = sentence_embeddings[i : i + 1]
        sim = float(_cosine_sim_matrix(prev_emb, curr_emb)[0, 0])
        candidate = " ".join(current + [sentences[i]])
        if sim >= merge_threshold and len(candidate) <= max_chars:
            current.append(sentences[i])
        else:
            chunk_text = " ".join(current).strip()
            if chunk_text:
                chunks.append(chunk_text)
            if overlap_sentences > 0 and current:
                tail = current[-overlap_sentences:]
                current = tail + [sentences[i]]
                candidate2 = " ".join(current).strip()
                if len(candidate2) > max_chars * 1.2:
                    current = [sentences[i]]
            else:
                current = [sentences[i]]
    last = " ".join(current).strip()
    if last:
        chunks.append(last)
    return [c for c in chunks if c]


def lexical_fallback_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = 100) -> list[str]:
    """تقسيم احتياطي بدون موديل (لـ TF-IDF أو عند تعذّر التضمين الجملي)."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    for para in paras:
        if len(para) <= max_chars:
            chunks.append(para)
            continue
        start = 0
        while start < len(para):
            end = min(start + max_chars, len(para))
            piece = para[start:end]
            if end < len(para):
                sp = piece.rfind(" ")
                if sp > max_chars // 2:
                    piece = piece[: sp + 1]
                    end = start + sp + 1
            chunks.append(piece.strip())
            start = end - overlap if overlap < max_chars else end
    return [c for c in chunks if c]


class SentenceTransformerBackend:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: _Encoder | None = None
        self._doc_matrix: np.ndarray | None = None

    def _load(self) -> _Encoder:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence-transformers model: %s", self.model_name)
            # Transformers الحديثة تطبع LOAD REPORT (مثل embeddings.position_ids UNEXPECTED)
            # عبر logger الجذر transformers — ليس loading_report فقط. خفض verbosity أثناء التحميل
            # يخفي التحذيرات دون تغيير الأوزان أو سلوك الاستنتاج.
            from transformers.utils import logging as hf_logging

            _prev_verbosity = hf_logging.get_verbosity()
            hf_logging.set_verbosity_error()
            try:
                self._model = cast(_Encoder, SentenceTransformer(self.model_name))
            finally:
                hf_logging.set_verbosity(_prev_verbosity)
        return self._model

    @property
    def model(self) -> _Encoder:
        """نفس المثيل المستخدم في التقسيم الدلالي والفهرس."""
        return self._load()

    def fit(self, texts: list[str]) -> None:
        model = self._load()
        if not texts:
            self._doc_matrix = np.zeros((0, 1), dtype=np.float32)
            return
        normalized = [normalize_arabic_for_embedding(t) for t in texts]
        emb = model.encode(
            normalized,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        self._doc_matrix = np.asarray(emb, dtype=np.float32)
        logger.info(
            "Built embedding matrix: shape=%s dtype=%s",
            self._doc_matrix.shape,
            self._doc_matrix.dtype,
        )

    def set_precomputed_embeddings(self, matrix: np.ndarray) -> None:
        """تحميل مصفوفة تضمينات جاهزة من الكاش دون إعادة fit."""
        self._doc_matrix = np.asarray(matrix, dtype=np.float32)
        logger.info(
            "Loaded precomputed embeddings: shape=%s",
            self._doc_matrix.shape,
        )

    def similarity_scores(self, expanded_query_norm: str) -> np.ndarray:
        model = self._load()
        docs = self._doc_matrix
        if docs is None or docs.size == 0:
            return np.array([], dtype=np.float32)
        q = expanded_query_norm.strip()
        if not q:
            return np.zeros((docs.shape[0],), dtype=np.float32)
        qv = model.encode(
            [q],
            batch_size=1,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        qv = np.asarray(qv, dtype=np.float32)
        return (qv @ docs.T)[0]

    @property
    def backend_name(self) -> str:
        return f"sentence-transformers:{self.model_name}"


class TfidfBackend:
    """احتياطي خفيف بدون torch — نفس التطبيع النصي على المدخلات."""

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(max_features=12000, ngram_range=(1, 2))
        self._matrix = None

    def fit(self, texts: list[str]) -> None:
        corpus = [normalize_arabic_for_embedding(t) for t in texts]
        if not corpus:
            self._matrix = None
            return
        self._matrix = self._vectorizer.fit_transform(corpus)

    def similarity_scores(self, expanded_query_norm: str) -> np.ndarray:
        from sklearn.metrics.pairwise import cosine_similarity

        if self._matrix is None:
            return np.array([], dtype=np.float32)
        qv = self._vectorizer.transform([expanded_query_norm])
        return np.asarray(cosine_similarity(qv, self._matrix)[0], dtype=np.float32)

    @property
    def backend_name(self) -> str:
        return "sklearn-tfidf(in-memory)"


@dataclass
class RagDocument:
    """مقطع للاسترجاع مع معرف الملف والقسم."""

    doc_id: str
    text: str
    department: str | None = None
    retrieval_meta: dict[str, Any] | None = None


class RagIndex:
    """
    RAG: تحميل JSON → نص طبي منظم → تقسيم دلالي → فهرس في الذاكرة → استرجاع دلالي + إعادة ترتيب خفيفة.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        backend: str = "sentence",
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
    ) -> None:
        self.model_name = model_name
        self._backend_mode = backend
        self.min_similarity = min_similarity
        self._backend: SentenceTransformerBackend | TfidfBackend | None = None

        self.documents: list[RagDocument] = []
        self._raw_documents: list[RagDocument] = []
        self._known_departments: set[str] = set()
        self._sentence_backend: SentenceTransformerBackend | None = None

    def _get_sentence_backend(self) -> SentenceTransformerBackend:
        if self._sentence_backend is None:
            self._sentence_backend = SentenceTransformerBackend(self.model_name)
        return self._sentence_backend

    def _maybe_downgrade_to_tfidf(self) -> None:
        if self._backend_mode != "sentence":
            return
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            logger.warning(
                "sentence-transformers غير مثبت — التقسيم المعجمي + فهرس TF-IDF محلياً."
            )
            self._backend_mode = "tfidf"

    def _create_backend(self) -> SentenceTransformerBackend | TfidfBackend:
        self._maybe_downgrade_to_tfidf()
        if self._backend_mode == "tfidf":
            return TfidfBackend()
        return self._get_sentence_backend()

    def _cache_paths(self) -> tuple[Path, Path, Path]:
        d = RAG_INDEX_CACHE_DIR
        return d / "manifest.json", d / "embeddings.npy", d / "chunks.json"

    def _try_load_disk_cache(self, data_fingerprint: str) -> bool:
        """يحمّل الفهرس من القرص إذا تطابقت البصمة واسم الموديل. يُستخدم مع backend sentence فقط."""
        if self._backend_mode != "sentence":
            return False
        man_path, emb_path, ch_path = self._cache_paths()
        if not man_path.is_file() or not emb_path.is_file() or not ch_path.is_file():
            return False
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("RAG cache: manifest read failed (%s)", e)
            return False
        if manifest.get("cache_version") != RAG_INDEX_CACHE_VERSION:
            return False
        if manifest.get("backend") != "sentence":
            return False
        if manifest.get("model_name") != self.model_name:
            logger.info("RAG cache: model changed — rebuilding index.")
            return False
        if manifest.get("data_fingerprint") != data_fingerprint:
            logger.info("RAG cache: RagData changed — rebuilding index.")
            return False
        try:
            emb = np.load(str(emb_path))
            emb = np.asarray(emb, dtype=np.float32)
            chunks_raw = json.loads(ch_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning("RAG cache: load failed (%s)", e)
            return False
        if not isinstance(chunks_raw, list) or len(chunks_raw) != emb.shape[0]:
            logger.warning(
                "RAG cache: chunks/embeddings length mismatch (%s vs %s).",
                len(chunks_raw) if isinstance(chunks_raw, list) else "?",
                emb.shape[0],
            )
            return False
        docs: list[RagDocument] = []
        depts: set[str] = set()
        for row in chunks_raw:
            if not isinstance(row, dict):
                return False
            dept = row.get("department")
            dept_str = str(dept).strip() if dept else None
            if dept_str:
                depts.add(normalize_arabic_for_embedding(dept_str))
            docs.append(
                RagDocument(
                    doc_id=str(row.get("doc_id", "")),
                    text=str(row.get("text", "")),
                    department=dept_str if dept_str else None,
                )
            )
        if not docs:
            return False
        backend = self._get_sentence_backend()
        backend.set_precomputed_embeddings(emb)
        self._backend = backend
        self.documents = docs
        self._known_departments = depts
        logger.info(
            "RAG: loaded %s chunks from disk cache (fingerprint ok).",
            len(docs),
        )
        return True

    def _save_disk_cache(self, data_fingerprint: str) -> None:
        """يحفظ التضمينات والمقاطع بعد بناء ناجح (sentence فقط)."""
        if self._backend_mode != "sentence":
            return
        backend = self._backend
        if not isinstance(backend, SentenceTransformerBackend):
            return
        matrix = backend._doc_matrix
        if matrix is None or matrix.size == 0:
            return
        if not self.documents or len(self.documents) != matrix.shape[0]:
            logger.warning("RAG cache: skip save — documents/matrix row mismatch.")
            return
        man_path, emb_path, ch_path = self._cache_paths()
        try:
            RAG_INDEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            arr = np.asarray(matrix, dtype=np.float32)
            tmp_emb = RAG_INDEX_CACHE_DIR / "_embeddings_write.npy"
            np.save(str(tmp_emb), arr)
            os.replace(tmp_emb, emb_path)

            chunks_payload = [
                {"doc_id": d.doc_id, "text": d.text, "department": d.department}
                for d in self.documents
            ]
            tmp_ch = RAG_INDEX_CACHE_DIR / "_chunks_write.json"
            tmp_ch.write_text(json.dumps(chunks_payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp_ch, ch_path)

            manifest = {
                "cache_version": RAG_INDEX_CACHE_VERSION,
                "backend": "sentence",
                "model_name": self.model_name,
                "data_fingerprint": data_fingerprint,
                "n_chunks": len(self.documents),
                "embedding_dim": int(matrix.shape[1]),
            }
            tmp_m = RAG_INDEX_CACHE_DIR / "_manifest_write.json"
            tmp_m.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp_m, man_path)
            logger.info("RAG: saved index cache under %s", RAG_INDEX_CACHE_DIR)
        except OSError as e:
            logger.warning("RAG cache: save failed (%s)", e)

    def load_documents(self) -> None:
        """المرحلة 1: قراءة JSON من GradData/RagData فقط."""
        docs: list[RagDocument] = []
        if not RAG_DIR.exists():
            logger.warning("RAG directory missing: %s", RAG_DIR)
            self._raw_documents = []
            return

        paths = sorted(RAG_DIR.glob("*.json"))
        self._known_departments.clear()
        errors: list[str] = []
        for json_path in paths:
            try:
                # utf-8-sig يزيل BOM ويقرأ الملفات المحفوظة من Excel/Notepad على ويندوز
                with json_path.open("r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    errors.append(f"{json_path.name}: expected object")
                    continue
                structured = build_structured_medical_text(data)
                if not structured:
                    errors.append(f"{json_path.name}: empty structured text")
                    continue
                raw_dept = str(data.get("department", "") or "").strip()
                dept_val = normalize_department_name(raw_dept) if raw_dept else None
                if dept_val:
                    self._known_departments.add(normalize_arabic_for_embedding(dept_val))
                docs.append(
                    RagDocument(
                        doc_id=json_path.name,
                        text=structured,
                        department=dept_val,
                    )
                )
            except json.JSONDecodeError as e:
                errors.append(f"{json_path.name}: JSON error — {e}")
            except OSError as e:
                errors.append(f"{json_path.name}: read error — {e}")

        self._raw_documents = docs
        logger.info(
            "Loaded %s JSON files; %s valid raw documents.",
            len(paths),
            len(self._raw_documents),
        )
        if errors:
            for msg in errors[:15]:
                logger.warning("RAG load: %s", msg)
            if len(errors) > 15:
                logger.warning("... and %s more load messages", len(errors) - 15)

    def _chunk_single_document(self, doc: RagDocument) -> list[RagDocument]:
        text = doc.text
        if not text.strip():
            return [doc]

        if self._backend_mode == "tfidf":
            parts = lexical_fallback_chunks(text)
        else:
            try:
                model = self._get_sentence_backend().model
                sentences = split_arabic_sentences(text)
                if len(sentences) <= 1 or len(text) < MIN_CHUNK_CHARS * 2:
                    parts = [text.strip()]
                else:
                    norm_sents = [normalize_arabic_for_embedding(s) for s in sentences]
                    emb = model.encode(
                        norm_sents,
                        batch_size=32,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                        normalize_embeddings=True,
                    )
                    emb_arr = np.asarray(emb, dtype=np.float32)
                    parts = semantic_merge_sentences(sentences, emb_arr)
                    if not parts:
                        parts = [text.strip()]
            except Exception as e:
                logger.warning(
                    "Semantic chunking failed for %s (%s); using lexical fallback.",
                    doc.doc_id,
                    e,
                )
                parts = lexical_fallback_chunks(text)

        out: list[RagDocument] = []
        for i, chunk in enumerate(parts):
            out.append(
                RagDocument(
                    doc_id=f"{doc.doc_id}#{i}",
                    text=chunk,
                    department=doc.department,
                )
            )
        return out if out else [doc]

    def chunk_documents(self) -> None:
        """المرحلة 2: تقسيم دلالي (أو احتياطي عند TF-IDF)."""
        self._maybe_downgrade_to_tfidf()
        if not self._raw_documents:
            self.load_documents()
        self.documents = []
        for doc in self._raw_documents:
            self.documents.extend(self._chunk_single_document(doc))
        logger.info("Total semantic/lexical chunks: %s", len(self.documents))

    def build_index(self) -> None:
        """المرحلة 3: بناء مصفوفة التضمين أو TF-IDF، مع تحميل من كاش القرص إن وُجد."""
        self._maybe_downgrade_to_tfidf()
        fp = rag_data_fingerprint()

        if self._try_load_disk_cache(fp):
            logger.info("Index backend: %s (from disk cache)", self._backend.backend_name)
            return

        if not self._raw_documents:
            self.load_documents()
        if not self.documents:
            self.chunk_documents()
        texts = [d.text for d in self.documents]
        if not texts:
            logger.warning("No chunks to index.")
            return

        self._backend = self._create_backend()
        self._backend.fit(texts)
        logger.info("Index backend: %s", self._backend.backend_name)
        if isinstance(self._backend, SentenceTransformerBackend):
            self._save_disk_cache(fp)

    def _semantic_scores(self, query: str) -> np.ndarray:
        if self._backend is None:
            return np.array([], dtype=np.float32)
        if not self.documents:
            return np.array([], dtype=np.float32)

        q_norm = normalize_arabic_for_embedding(query)
        q_expanded = expand_query_synonyms(q_norm)
        return self._backend.similarity_scores(q_expanded)

    def _department_hint_score(self, query_norm: str, dept: str | None) -> float:
        if not dept:
            return 0.0
        d_norm = normalize_arabic_for_embedding(dept)
        if not d_norm:
            return 0.0
        if d_norm in query_norm or any(
            part in query_norm for part in d_norm.split() if len(part) > 3
        ):
            return DEPARTMENT_MATCH_BONUS
        for known in self._known_departments:
            if len(known) > 5 and known in query_norm and known in d_norm:
                return DEPARTMENT_MATCH_BONUS * 0.75
        return 0.0

    @staticmethod
    def _token_jaccard(a: str, b: str) -> float:
        ta = set(a.split())
        tb = set(b.split())
        if not ta or not tb:
            return 0.0
        inter = len(ta & tb)
        union = len(ta | tb)
        return inter / union if union else 0.0

    @staticmethod
    def _symptom_overlap_score(query_norm: str, chunk_text: str) -> float:
        """تطابق مفردات مرادفة/أعراض بين الاستعلام والمقطع."""
        chunk_n = normalize_arabic_for_embedding(chunk_text)
        hits = 0
        total = 0
        for canon, alts in SYMPTOM_SYNONYM_GROUPS.items():
            total += 1
            bag = (canon,) + alts
            if any(x in query_norm for x in bag) and any(x in chunk_n for x in bag):
                hits += 1
        return min(1.0, hits / max(8, len(SYMPTOM_SYNONYM_GROUPS) // 2))

    @staticmethod
    def _critical_phrase_score(query_norm: str, chunk_text: str) -> float:
        chunk_n = normalize_arabic_for_embedding(chunk_text)
        hits = 0
        for ph in CRITICAL_MEDICAL_PHRASES:
            pn = normalize_arabic_for_embedding(ph)
            if pn in query_norm and pn in chunk_n:
                hits += 1
        return min(1.0, hits / 3.0)

    def _rerank(
        self,
        query_raw: str,
        candidates: list[tuple[int, float]],
    ) -> list[tuple[int, float, dict[str, Any]]]:
        q_norm = normalize_arabic_for_embedding(query_raw)
        reranked: list[tuple[int, float, dict[str, Any]]] = []
        for idx, sem in candidates:
            doc = self.documents[idx]
            sym = self._symptom_overlap_score(q_norm, doc.text)
            jac = self._token_jaccard(q_norm, normalize_arabic_for_embedding(doc.text))
            dept = self._department_hint_score(q_norm, doc.department)
            crit = self._critical_phrase_score(q_norm, doc.text)
            combined = (
                RERANK_WEIGHT_SEMANTIC * sem
                + RERANK_WEIGHT_SYMPTOM_OVERLAP * sym
                + RERANK_WEIGHT_TOKEN_JACCARD * jac
                + RERANK_WEIGHT_DEPARTMENT * min(1.0, dept / max(DEPARTMENT_MATCH_BONUS, 1e-6))
                + RERANK_WEIGHT_CRITICAL * crit
            )
            meta = {
                "semantic_score": round(float(sem), 4),
                "symptom_overlap": round(float(sym), 4),
                "token_jaccard": round(float(jac), 4),
                "department_boost": round(float(dept), 4),
                "critical_phrase": round(float(crit), 4),
                "rerank_combined": round(float(combined), 4),
            }
            reranked.append((idx, combined, meta))
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked

    def retrieve(self, query: str, top_k: int = 3) -> list[RagDocument]:
        pairs = self.retrieve_with_scores(query, top_k=top_k)
        return [d for d, _ in pairs]

    def retrieve_with_scores(
        self,
        query: str,
        top_k: int = 3,
        *,
        min_score: float | None = None,
        rerank: bool = True,
    ) -> list[tuple[RagDocument, float]]:
        """
        استرجاع دلالي مع درجة (بعد إعادة الترتيب الخفيفة).
        min_score: حد أدنى للتشابه الدلالي الأولي قبل إعادة الترتيب.
        """
        threshold = self.min_similarity if min_score is None else float(min_score)
        if self._backend is None:
            self.build_index()
        if not self.documents:
            logger.warning("retrieve_with_scores: empty index")
            return []

        sims = self._semantic_scores(query)
        if sims.size == 0:
            return []

        pool_size = min(DEFAULT_RETRIEVAL_TOP_POOL, len(sims))
        order = np.argsort(sims)[::-1][:pool_size]
        candidates: list[tuple[int, float]] = []
        for i in order:
            si = float(sims[int(i)])
            if si < threshold:
                continue
            candidates.append((int(i), si))
        if not candidates:
            logger.info(
                "No chunks above threshold=%s (max_sim=%.4f)",
                threshold,
                float(np.max(sims)) if sims.size else 0.0,
            )
            return []

        if rerank:
            reranked = self._rerank(query, candidates)
            final = reranked[:top_k]
        else:
            final = [(i, s, {"semantic_score": s}) for i, s in candidates[:top_k]]

        out: list[tuple[RagDocument, float]] = []
        for idx, score, meta in final:
            doc = self.documents[idx]
            doc_copy = RagDocument(
                doc_id=doc.doc_id,
                text=doc.text,
                department=doc.department,
                retrieval_meta=meta,
            )
            out.append((doc_copy, float(score)))
        logger.info(
            "Retrieved %s results for query (top_k=%s, threshold=%s)",
            len(out),
            top_k,
            threshold,
        )
        return out

    def debug_inspect(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """
        أدوات فحص أثناء التطوير: الاستعلام بعد التطبيع والتوسيع، أعلى المقاطع، الدرجات، وأسباب إعادة الترتيب.
        """
        q_norm = normalize_arabic_for_embedding(query)
        q_exp = expand_query_synonyms(q_norm)
        if self._backend is None:
            self.build_index()
        sims = self._semantic_scores(query) if self.documents else np.array([])
        top_idx = np.argsort(sims)[::-1][:20] if sims.size else np.array([], dtype=int)
        pre_rerank = [(int(i), float(sims[int(i)])) for i in top_idx if sims[int(i)] >= self.min_similarity]
        pairs = self.retrieve_with_scores(query, top_k=top_k, rerank=True)
        return {
            "query_normalized": q_norm,
            "query_synonym_expanded": q_exp,
            "backend": getattr(self._backend, "backend_name", None),
            "min_similarity_config": self.min_similarity,
            "top_pre_rerank_semantic": pre_rerank[:10],
            "retrieval_results": [
                {
                    "doc_id": d.doc_id,
                    "department": d.department,
                    "score": round(s, 5),
                    "text_preview": d.text[:400] + ("…" if len(d.text) > 400 else ""),
                    "rerank_meta": d.retrieval_meta,
                }
                for d, s in pairs
            ],
        }


rag_index = RagIndex()
