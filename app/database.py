from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "hospital.db"


class Base(DeclarativeBase):
    pass


# timeout: انتظار قفل الملف (ثوانٍ) بدل فشل فوري — مفيد مع --reload وعدة اتصالات.
# check_same_thread: السماح باستعمال نفس الـ engine من خيوط (مثلاً RAG) مع SQLite.
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30.0},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _sqlite_on_connect(dbapi_connection, _):
    # WAL يخفّف تعارض القراءة/الكتابة ويقلّل "database is locked" على Windows.
    cur = dbapi_connection.cursor()
    try:
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
    finally:
        cur.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_doctors_view() -> None:
    """
    إنشاء View في قاعدة البيانات يعرض الأطباء مع اسم القسم (أي قسم الطبيب تابع له).
    عند فتح hospital.db يمكن فتح الجدول doctors_with_department بدل doctors لرؤية اسم القسم.
    """
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE VIEW IF NOT EXISTS doctors_with_department AS "
                "SELECT d.id, d.full_name, d.department_id, dep.name AS department_name "
                "FROM doctors d LEFT JOIN departments dep ON d.department_id = dep.id"
            )
        )
        conn.commit()


def migrate_chat_sessions() -> None:
    """إضافة أعمدة الـ Multi-Agent Architecture لجدول chat_sessions (للقواعد الموجودة)."""
    new_columns = [
        ("shared_memory", "TEXT DEFAULT '{}'"),
        ("stop_signal", "BOOLEAN DEFAULT 0"),
        ("stability_counter", "INTEGER DEFAULT 0"),
        ("last_top_department", "VARCHAR(100)"),
        ("department_confidence", "REAL DEFAULT 0.0"),
    ]
    with engine.connect() as conn:
        for col_name, col_def in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE chat_sessions ADD COLUMN {col_name} {col_def}"))
            except Exception:
                pass
        conn.commit()


def ensure_evaluation_table() -> None:
    """
    إنشاء جدول evaluation_traces إن لم يكن موجوداً.
    جدول مستقل تماماً — لا علاقة له بأي بيانات طبية/جلسات/مواعيد.
    """
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS evaluation_traces ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "session_id INTEGER NOT NULL, "
                "trace_scope VARCHAR(20) NOT NULL DEFAULT 'turn', "
                "turn_index INTEGER NOT NULL DEFAULT 0, "
                "created_at DATETIME NOT NULL, "
                "model_used VARCHAR(100) NOT NULL, "
                "asking_total INTEGER DEFAULT 0, "
                "asking_max INTEGER DEFAULT 18, "
                "asking_ratio REAL, "
                "department_total INTEGER DEFAULT 0, "
                "department_max INTEGER DEFAULT 9, "
                "department_ratio REAL, "
                "structured_total INTEGER DEFAULT 0, "
                "structured_max INTEGER DEFAULT 6, "
                "structured_ratio REAL, "
                "emergency_total INTEGER DEFAULT 0, "
                "emergency_max INTEGER DEFAULT 4, "
                "emergency_ratio REAL, "
                "system_conversation_score REAL, "
                "scores_json TEXT DEFAULT '{}', "
                "snapshot_json TEXT DEFAULT '{}', "
                "error TEXT"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_evaluation_traces_session "
                "ON evaluation_traces(session_id)"
            )
        )
        try:
            conn.execute(
                text(
                    "ALTER TABLE evaluation_traces "
                    "ADD COLUMN trace_scope VARCHAR(20) NOT NULL DEFAULT 'turn'"
                )
            )
        except Exception:
            pass
        extra_columns = [
            ("asking_ratio", "REAL"),
            ("department_ratio", "REAL"),
            ("structured_ratio", "REAL"),
            ("emergency_ratio", "REAL"),
            ("system_conversation_score", "REAL"),
        ]
        for col_name, col_def in extra_columns:
            try:
                conn.execute(
                    text(
                        f"ALTER TABLE evaluation_traces "
                        f"ADD COLUMN {col_name} {col_def}"
                    )
                )
            except Exception:
                pass
        conn.execute(
            text(
                "UPDATE evaluation_traces "
                "SET trace_scope = COALESCE(trace_scope, 'turn') "
                "WHERE trace_scope IS NULL OR trace_scope = ''"
            )
        )
        conn.commit()


def ensure_department_decisions_table() -> None:
    """إنشاء جدول حفظ قرارات Department Agent لكل turn."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS evaluation_department_decisions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "session_id INTEGER NOT NULL, "
                "turn_index INTEGER NOT NULL, "
                "created_at DATETIME NOT NULL, "
                "top_department VARCHAR(100) NOT NULL, "
                "confidence REAL DEFAULT 0.0, "
                "scores_json TEXT DEFAULT '{}', "
                "reason TEXT DEFAULT ''"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_eval_dept_decisions_session "
                "ON evaluation_department_decisions(session_id)"
            )
        )
        conn.commit()


def migrate_evaluation_traces_rubric() -> None:
    """
    مزامنة سجلات evaluation_traces مع الروبريك الجديد لوكيل الطوارئ:
    - حذف البعد الثالث القديم من scores_json
    - إعادة حساب emergency_total
    - تثبيت emergency_max = 4
    """
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text("SELECT id, scores_json FROM evaluation_traces")
            ).fetchall()
        except Exception:
            return

        for row in rows:
            raw = row[1] or "{}"
            try:
                data = json.loads(raw)
            except Exception:
                conn.execute(
                    text(
                        "UPDATE evaluation_traces "
                        "SET emergency_max = 4 "
                        "WHERE id = :id"
                    ),
                    {"id": row[0]},
                )
                continue

            dims = data.get("dimensions", {}) or {}
            dims.pop("emerg_dim3_risk_reasoning", None)
            emergency_total = 0
            for dim_data in dims.values():
                if dim_data.get("agent") == "emergency":
                    try:
                        emergency_total += int(dim_data.get("score", 1))
                    except Exception:
                        emergency_total += 1

            maxes = data.get("maxes", {}) or {}
            maxes["emergency"] = 4
            data["maxes"] = maxes

            totals = data.get("totals", {}) or {}
            totals["emergency"] = emergency_total
            data["totals"] = totals

            conn.execute(
                text(
                    "UPDATE evaluation_traces "
                    "SET emergency_total = :emergency_total, "
                    "    emergency_max = 4, "
                    "    scores_json = :scores_json "
                    "WHERE id = :id"
                ),
                {
                    "id": row[0],
                    "emergency_total": emergency_total,
                    "scores_json": json.dumps(data, ensure_ascii=False),
                },
            )
        conn.commit()


def migrate_evaluation_logic_split() -> None:
    """
    مواءمة السجلات القديمة مع المنطق الجديد:
    - turn traces تحتوي فقط على Asking 1..5 + Structured 1..2
    - حذف Department/Emergency/Asking dim6 من سجلات turn القديمة
    - إعادة حساب totals/maxes
    - backfill جدول evaluation_department_decisions من snapshot_json القديم
    """
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text(
                    "SELECT id, session_id, turn_index, trace_scope, scores_json, snapshot_json "
                    "FROM evaluation_traces"
                )
            ).fetchall()
        except Exception:
            return

        for row in rows:
            row_id, session_id, turn_index, trace_scope, scores_raw, snapshot_raw = row
            trace_scope = trace_scope or "turn"

            try:
                scores_data = json.loads(scores_raw or "{}")
            except Exception:
                scores_data = {}

            if trace_scope == "turn":
                dims = scores_data.get("dimensions", {}) or {}
                keys_to_remove = [
                    "ask_dim6_denial_handling",
                    "dept_dim1_selection_accuracy",
                    "dept_dim2_reasoning",
                    "dept_dim3_stability",
                    "emerg_dim1_detection_accuracy",
                    "emerg_dim2_false_positive_control",
                    "emerg_dim3_risk_reasoning",
                ]
                for key in keys_to_remove:
                    dims.pop(key, None)

                asking_total = 0
                structured_total = 0
                for key, dim in dims.items():
                    try:
                        score = int(dim.get("score", 1))
                    except Exception:
                        score = 1
                    if key.startswith("ask_dim"):
                        asking_total += score
                    elif key.startswith("struct_dim"):
                        structured_total += score

                scores_data["dimensions"] = dims
                scores_data["totals"] = {
                    "asking": asking_total,
                    "department": 0,
                    "structured": structured_total,
                    "emergency": 0,
                }
                scores_data["maxes"] = {
                    "asking": 15,
                    "department": 0,
                    "structured": 6,
                    "emergency": 0,
                }
                scores_data["trace_scope"] = "turn"

                conn.execute(
                    text(
                        "UPDATE evaluation_traces "
                        "SET trace_scope = 'turn', "
                        "    asking_total = :asking_total, "
                        "    asking_max = 15, "
                        "    department_total = 0, "
                        "    department_max = 0, "
                        "    structured_total = :structured_total, "
                        "    structured_max = 6, "
                        "    emergency_total = 0, "
                        "    emergency_max = 0, "
                        "    scores_json = :scores_json "
                        "WHERE id = :id"
                    ),
                    {
                        "id": row_id,
                        "asking_total": asking_total,
                        "structured_total": structured_total,
                        "scores_json": json.dumps(scores_data, ensure_ascii=False),
                    },
                )

            try:
                snapshot = json.loads(snapshot_raw or "{}")
            except Exception:
                snapshot = {}

            dept_output = snapshot.get("department_output") or {}
            top_department = str(dept_output.get("top_department") or "").strip()
            if trace_scope == "turn" and top_department:
                exists = conn.execute(
                    text(
                        "SELECT id FROM evaluation_department_decisions "
                        "WHERE session_id = :session_id AND turn_index = :turn_index "
                        "LIMIT 1"
                    ),
                    {"session_id": session_id, "turn_index": turn_index},
                ).fetchone()
                if not exists:
                    conn.execute(
                        text(
                            "INSERT INTO evaluation_department_decisions "
                            "(session_id, turn_index, created_at, top_department, confidence, scores_json, reason) "
                            "VALUES (:session_id, :turn_index, CURRENT_TIMESTAMP, :top_department, :confidence, :scores_json, :reason)"
                        ),
                        {
                            "session_id": session_id,
                            "turn_index": turn_index,
                            "top_department": top_department,
                            "confidence": float(dept_output.get("confidence", 0.0) or 0.0),
                            "scores_json": json.dumps(dept_output.get("scores", {}), ensure_ascii=False),
                            "reason": str(dept_output.get("reason", "") or ""),
                        },
                    )
        conn.commit()


def format_evaluation_json_columns() -> None:
    """
    إعادة تنسيق أعمدة JSON الخاصة بالتقييم لتكون مقروءة داخل DB Browser
    بدل أن تظهر كسطر واحد طويل.
    """
    with engine.connect() as conn:
        try:
            trace_rows = conn.execute(
                text("SELECT id, scores_json, snapshot_json FROM evaluation_traces")
            ).fetchall()
        except Exception:
            trace_rows = []

        for row in trace_rows:
            scores_raw = row[1] or "{}"
            snapshot_raw = row[2] or "{}"
            try:
                scores_pretty = json.dumps(json.loads(scores_raw), ensure_ascii=False, indent=2)
            except Exception:
                scores_pretty = scores_raw
            try:
                snapshot_pretty = json.dumps(json.loads(snapshot_raw), ensure_ascii=False, indent=2)
            except Exception:
                snapshot_pretty = snapshot_raw
            conn.execute(
                text(
                    "UPDATE evaluation_traces "
                    "SET scores_json = :scores_json, snapshot_json = :snapshot_json "
                    "WHERE id = :id"
                ),
                {
                    "id": row[0],
                    "scores_json": scores_pretty,
                    "snapshot_json": snapshot_pretty,
                },
            )

        try:
            decision_rows = conn.execute(
                text("SELECT id, scores_json FROM evaluation_department_decisions")
            ).fetchall()
        except Exception:
            decision_rows = []

        for row in decision_rows:
            raw = row[1] or "{}"
            try:
                pretty = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
            except Exception:
                pretty = raw
            conn.execute(
                text(
                    "UPDATE evaluation_department_decisions "
                    "SET scores_json = :scores_json "
                    "WHERE id = :id"
                ),
                {"id": row[0], "scores_json": pretty},
            )

        conn.commit()


def recompute_conversation_summary_columns() -> None:
    """
    حساب الأعمدة النهائية للمحادثة على سطر conversation فقط:
    - asking_ratio
    - department_ratio
    - structured_ratio
    - emergency_ratio
    - system_conversation_score
    وتبقى NULL في turn traces.
    """
    def _ratio(total: int, max_value: int) -> float | None:
        if not max_value or max_value <= 0:
            return None
        return round(float(total) / float(max_value), 6)

    with engine.connect() as conn:
        try:
            session_rows = conn.execute(
                text("SELECT DISTINCT session_id FROM evaluation_traces")
            ).fetchall()
        except Exception:
            return

        conn.execute(
            text(
                "UPDATE evaluation_traces SET "
                "asking_ratio = NULL, "
                "department_ratio = NULL, "
                "structured_ratio = NULL, "
                "emergency_ratio = NULL, "
                "system_conversation_score = NULL "
                "WHERE trace_scope = 'turn'"
            )
        )

        for (session_id,) in session_rows:
            conv = conn.execute(
                text(
                    "SELECT id, asking_total, asking_max, department_total, department_max, "
                    "structured_total, structured_max, emergency_total, emergency_max "
                    "FROM evaluation_traces "
                    "WHERE session_id = :session_id AND trace_scope = 'conversation' "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"session_id": session_id},
            ).fetchone()
            if not conv:
                continue

            turn_sum = conn.execute(
                text(
                    "SELECT "
                    "COALESCE(SUM(asking_total), 0), "
                    "COALESCE(SUM(asking_max), 0), "
                    "COALESCE(SUM(structured_total), 0), "
                    "COALESCE(SUM(structured_max), 0) "
                    "FROM evaluation_traces "
                    "WHERE session_id = :session_id AND trace_scope = 'turn'"
                ),
                {"session_id": session_id},
            ).fetchone()

            asking_total_all = int(turn_sum[0] or 0) + int(conv[1] or 0)
            asking_max_all = int(turn_sum[1] or 0) + int(conv[2] or 0)
            structured_total_all = int(turn_sum[2] or 0)
            structured_max_all = int(turn_sum[3] or 0)
            department_total = int(conv[3] or 0)
            department_max = int(conv[4] or 0)
            emergency_total = int(conv[7] or 0)
            emergency_max = int(conv[8] or 0)

            asking_ratio = _ratio(asking_total_all, asking_max_all)
            department_ratio = _ratio(department_total, department_max)
            structured_ratio = _ratio(structured_total_all, structured_max_all)
            emergency_ratio = _ratio(emergency_total, emergency_max)

            ratios = [
                asking_ratio or 0.0,
                department_ratio or 0.0,
                structured_ratio or 0.0,
                emergency_ratio or 0.0,
            ]
            system_conversation_score = round(sum(ratios) / 4.0, 6)

            conn.execute(
                text(
                    "UPDATE evaluation_traces SET "
                    "asking_ratio = :asking_ratio, "
                    "department_ratio = :department_ratio, "
                    "structured_ratio = :structured_ratio, "
                    "emergency_ratio = :emergency_ratio, "
                    "system_conversation_score = :system_conversation_score "
                    "WHERE id = :id"
                ),
                {
                    "id": conv[0],
                    "asking_ratio": asking_ratio,
                    "department_ratio": department_ratio,
                    "structured_ratio": structured_ratio,
                    "emergency_ratio": emergency_ratio,
                    "system_conversation_score": system_conversation_score,
                },
            )
        conn.commit()


def get_db():
    from sqlalchemy.orm import Session

    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

