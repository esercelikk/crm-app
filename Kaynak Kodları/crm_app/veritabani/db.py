from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import sqlite3
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..yetki import ROLE_GOALS, ROLE_OPTIONS

MONTH_LABELS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
STAGE_ORDER = ["Potansiyel", "Görüşme", "Teklif", "Kazanıldı", "Kaybedildi"]
STATUS_OPTIONS = ["Aktif", "Beklemede", "Riskli", "Pasif"]
TAG_OPTIONS = ["Yeni", "Takip", "Önemli", "Kurumsal", "Pasif"]
PRIORITY_OPTIONS = ["Yüksek", "Orta", "Düşük"]
CALL_TYPE_OPTIONS = ["Telefon", "Toplantı", "Email"]
CALL_OUTCOME_OPTIONS = ["Olumlu", "Beklemede", "Olumsuz", "Riskli"]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def first_day_of_month(value: date) -> date:
    return value.replace(day=1)


def add_months(value: date, delta: int) -> date:
    month_index = value.month - 1 + delta
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        # Veritabanı yolunu kullanıcının appdata dizinine ayarla (kalıcı ve yazılabilir)
        appdata_dir = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        self.data_dir = appdata_dir / "NexCRM" / "data"
        self.upload_dir = self.data_dir / "uploads"
        self.report_dir = self.data_dir / "reports"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = Path(db_path) if db_path else self.data_dir / "nexcrm.sqlite"
        # The app reads/writes the DB from UI and worker threads (AI replies).
        # Allow cross-thread usage and serialize access with an internal lock.
        self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.setup()

    def setup(self) -> None:
        self.create_tables()
        self.seed_defaults()
        self.normalize_contact_tags()
        self.ensure_runtime_notifications()

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def execute(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cursor = self.connection.execute(query, tuple(params))
            self.connection.commit()
            return cursor

    def executemany(self, query: str, params: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
        with self._lock:
            cursor = self.connection.executemany(query, params)
            self.connection.commit()
            return cursor

    def fetchone(self, query: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.connection.execute(query, tuple(params)).fetchone()
            return dict(row) if row else None

    def fetchall(self, query: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(query, tuple(params)).fetchall()
            return [dict(row) for row in rows]

    def create_tables(self) -> None:
        with self._lock:
            self.connection.executescript(
                """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_login TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                company TEXT NOT NULL,
                title TEXT,
                phone TEXT,
                whatsapp TEXT,
                email TEXT,
                city TEXT,
                country TEXT,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                tag TEXT NOT NULL,
                notes TEXT,
                assigned_user_id INTEGER,
                payment_score INTEGER NOT NULL DEFAULT 70,
                potential_score INTEGER NOT NULL DEFAULT 70,
                loyalty_score INTEGER NOT NULL DEFAULT 70,
                churn_risk INTEGER NOT NULL DEFAULT 20,
                ai_score INTEGER NOT NULL DEFAULT 70,
                last_contact_at TEXT,
                reminder_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                stage TEXT NOT NULL,
                value REAL NOT NULL DEFAULT 0,
                probability INTEGER NOT NULL DEFAULT 0,
                expected_close TEXT,
                notes TEXT,
                owner_user_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT,
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
                FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                call_type TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL DEFAULT 0,
                outcome TEXT NOT NULL,
                notes TEXT,
                reminder_at TEXT,
                owner_user_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
                FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT NOT NULL,
                due_at TEXT,
                status TEXT NOT NULL DEFAULT 'Bekliyor',
                is_done INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                assigned_user_id INTEGER,
                contact_id INTEGER,
                owner_user_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                template_name TEXT,
                status TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT 'Giden',
                is_unread INTEGER NOT NULL DEFAULT 0,
                sent_at TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                category TEXT NOT NULL,
                mime_type TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                uploaded_by INTEGER,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL,
                FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                author_user_id INTEGER,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
                FOREIGN KEY (author_user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                related_contact_id INTEGER,
                related_user_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (related_contact_id) REFERENCES contacts(id) ON DELETE SET NULL,
                FOREIGN KEY (related_user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                action_view TEXT,
                action_entity_id INTEGER,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mail_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                subject TEXT NOT NULL,
                body TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS automations (
                key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            """
            )
            self.connection.commit()

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
        actual_salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            actual_salt.encode("utf-8"),
            120_000,
        ).hex()
        return digest, actual_salt

    def compute_ai_score(
        self,
        payment_score: Any,
        potential_score: Any,
        loyalty_score: Any,
        churn_risk: Any,
    ) -> int:
        payment = min(max(safe_int(payment_score, 70), 0), 100)
        potential = min(max(safe_int(potential_score, 70), 0), 100)
        loyalty = min(max(safe_int(loyalty_score, 70), 0), 100)
        churn = min(max(safe_int(churn_risk, 20), 0), 100)
        blended = payment * 0.34 + potential * 0.34 + loyalty * 0.22 + (100 - churn) * 0.10
        return int(round(blended))

    def normalize_contact_tags(self) -> None:
        mapping = {
            "VIP": "Önemli",
            "Öncelikli": "Önemli",
            "Sıcak": "Önemli",
            "Enterprise": "Kurumsal",
            "Potansiyel": "Takip",
            "Takipte": "Takip",
            "Soğuk": "Pasif",
        }
        for old_value, new_value in mapping.items():
            self.execute(
                "UPDATE contacts SET tag = ?, updated_at = ? WHERE tag = ?",
                (new_value, now_iso(), old_value),
            )

    def auto_compute_contact_scores(self, contact_id: int) -> Dict[str, int]:
        """Müşterinin faaliyetlerine göre AI skorlarını otomatik hesaplar."""
        won_total = self.fetchone(
            "SELECT COALESCE(SUM(value), 0) AS total FROM opportunities WHERE contact_id = ? AND stage = 'Kazanıldı'",
            (contact_id,),
        )
        won_value = float(won_total["total"]) if won_total else 0

        open_pipeline = self.fetchone(
            "SELECT COALESCE(SUM(value), 0) AS total, COUNT(*) AS cnt FROM opportunities WHERE contact_id = ? AND stage NOT IN ('Kazanıldı', 'Kaybedildi')",
            (contact_id,),
        )
        open_value = float(open_pipeline["total"]) if open_pipeline else 0
        open_count = int(open_pipeline["cnt"]) if open_pipeline else 0

        call_stats = self.fetchone(
            "SELECT COUNT(*) AS cnt, MAX(scheduled_at) AS last_call FROM calls WHERE contact_id = ?",
            (contact_id,),
        )
        call_count = int(call_stats["cnt"]) if call_stats else 0
        last_call_at = parse_iso(call_stats["last_call"]) if call_stats and call_stats["last_call"] else None

        positive_calls = self.fetchone(
            "SELECT COUNT(*) AS cnt FROM calls WHERE contact_id = ? AND outcome = 'Olumlu'",
            (contact_id,),
        )
        positive_count = int(positive_calls["cnt"]) if positive_calls else 0

        contact = self.fetchone("SELECT last_contact_at, created_at FROM contacts WHERE id = ?", (contact_id,))
        last_contact = parse_iso(contact["last_contact_at"]) if contact and contact["last_contact_at"] else None
        days_since_contact = (datetime.now() - last_contact).days if last_contact else 60

        # Payment score: kazanılan satışlara göre (0-200K arası 0-100)
        payment_score = min(100, int(round((won_value / 200000) * 100))) if won_value > 0 else 40

        # Potential score: açık pipeline + olumlu görüşme oranı
        pipeline_factor = min(50, int(round((open_value / 50000) * 50)))
        positive_ratio = (positive_count / max(call_count, 1)) * 50 if call_count > 0 else 25
        potential_score = min(100, int(round(pipeline_factor + positive_ratio)))

        # Loyalty score: görüşme sayısı + son temas yakınlığı
        call_factor = min(50, call_count * 10)
        recency_factor = max(0, 50 - days_since_contact * 2)
        loyalty_score = min(100, int(round(call_factor + recency_factor)))

        # Müşteri riski: temas sıklığı ve olumsuz görüşmeler dengeli ilerlesin.
        if days_since_contact <= 7:
            churn_base = 8
        elif days_since_contact <= 14:
            churn_base = 16
        elif days_since_contact <= 30:
            churn_base = 28
        elif days_since_contact <= 45:
            churn_base = 42
        else:
            churn_base = min(68, 42 + int((days_since_contact - 45) / 3))

        negative_calls = self.fetchone(
            "SELECT COUNT(*) AS cnt FROM calls WHERE contact_id = ? AND outcome IN ('Olumsuz', 'Riskli')",
            (contact_id,),
        )
        negative_count = int(negative_calls["cnt"]) if negative_calls else 0
        negative_ratio = (negative_count / max(call_count, 1)) * 24 if call_count > 0 else 6
        active_pipeline_bonus = 8 if open_value > 0 and positive_count > 0 else 0
        churn_risk = max(5, min(100, int(round(churn_base + negative_ratio - active_pipeline_bonus))))

        ai_score = self.compute_ai_score(payment_score, potential_score, loyalty_score, churn_risk)

        return {
            "payment_score": payment_score,
            "potential_score": potential_score,
            "loyalty_score": loyalty_score,
            "churn_risk": churn_risk,
            "ai_score": ai_score,
        }

    def refresh_contact_scores(self, contact_id: int) -> None:
        """Müşterinin AI skorlarını yeniden hesaplar ve günceller."""
        scores = self.auto_compute_contact_scores(contact_id)
        self.execute(
            """
            UPDATE contacts
            SET payment_score = ?, potential_score = ?, loyalty_score = ?, churn_risk = ?, ai_score = ?, updated_at = ?
            WHERE id = ?
            """,
            (scores["payment_score"], scores["potential_score"], scores["loyalty_score"],
             scores["churn_risk"], scores["ai_score"], now_iso(), contact_id),
        )

    def refresh_all_contact_scores(self) -> None:
        """Tüm müşterilerin AI skorlarını yeniden hesaplar."""
        contacts = self.fetchall("SELECT id FROM contacts")
        for contact in contacts:
            self.refresh_contact_scores(contact["id"])

    def probability_for_stage(self, stage: str) -> int:
        mapping = {
            "Potansiyel": 35,
            "Görüşme": 62,
            "Teklif": 84,
            "Kazanıldı": 100,
            "Kaybedildi": 0,
        }
        return mapping.get(stage, 50)

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def create_notification(
        self,
        title: str,
        message: str,
        severity: str = "Bilgi",
        action_view: Optional[str] = None,
        action_entity_id: Optional[int] = None,
        user_id: Optional[int] = None,
        dedupe_key: Optional[str] = None,
    ) -> None:
        if dedupe_key:
            exists = self.fetchone(
                "SELECT id FROM notifications WHERE title = ? AND message = ?",
                (title, message),
            )
            if exists:
                return
        self.execute(
            """
            INSERT INTO notifications(user_id, title, message, severity, action_view, action_entity_id, is_read, created_at)
            VALUES(?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (user_id, title, message, severity, action_view, action_entity_id, now_iso()),
        )

    def mark_notification_read(self, notification_id: int) -> None:
        self.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))

    def list_notifications(self, unread_first: bool = True) -> List[Dict[str, Any]]:
        order = "is_read ASC, datetime(created_at) DESC" if unread_first else "datetime(created_at) DESC"
        return self.fetchall(f"SELECT * FROM notifications ORDER BY {order} LIMIT 20")

    def record_activity(
        self,
        kind: str,
        entity_type: str,
        entity_id: Optional[int],
        title: str,
        description: str,
        related_contact_id: Optional[int] = None,
        related_user_id: Optional[int] = None,
        created_at: Optional[str] = None,
    ) -> None:
        self.execute(
            """
            INSERT INTO activities(kind, entity_type, entity_id, title, description, related_contact_id, related_user_id, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kind,
                entity_type,
                entity_id,
                title,
                description,
                related_contact_id,
                related_user_id,
                created_at or now_iso(),
            ),
        )

    def list_activities(self, limit: int = 10, contact_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT a.*, c.full_name AS contact_name
            FROM activities a
            LEFT JOIN contacts c ON c.id = a.related_contact_id
        """
        params: List[Any] = []
        if contact_id:
            query += " WHERE a.related_contact_id = ?"
            params.append(contact_id)
        query += " ORDER BY datetime(a.created_at) DESC LIMIT ?"
        params.append(limit)
        return self.fetchall(query, params)

    def list_user_activities(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT a.*, c.full_name AS contact_name
            FROM activities a
            LEFT JOIN contacts c ON c.id = a.related_contact_id
            WHERE a.related_user_id = ?
            ORDER BY datetime(a.created_at) DESC
            LIMIT ?
            """,
            (user_id, limit),
        )

    def list_mail_templates(self) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM mail_templates ORDER BY name")

    def get_mail_template(self, name: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM mail_templates WHERE name = ?", (name,))

    def list_automations(self) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM automations ORDER BY label")

    def set_automation_enabled(self, key: str, enabled: bool) -> None:
        self.execute("UPDATE automations SET enabled = ? WHERE key = ?", (1 if enabled else 0, key))

    def authenticate_user(self, email: str, password: str, remember_me: bool = False) -> tuple[Optional[Dict[str, Any]], str]:
        user = self.fetchone("SELECT * FROM users WHERE lower(email) = lower(?)", (email.strip(),))
        if not user:
            return None, "Bu e-posta ile kayıtlı kullanıcı bulunamadı."
        if not user["is_active"]:
            return None, "Bu kullanıcı pasif durumda."
        digest, _ = self.hash_password(password, user["password_salt"])
        if digest != user["password_hash"]:
            return None, "Şifre hatalı."

        now = now_iso()
        self.execute("UPDATE users SET last_login = ?, updated_at = ? WHERE id = ?", (now, now, user["id"]))
        self.set_setting("remembered_email", user["email"] if remember_me else "")
        refreshed = self.get_user(user["id"])
        return refreshed, ""

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    def list_users(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT
                u.*,
                COALESCE((SELECT COUNT(*) FROM contacts c WHERE c.assigned_user_id = u.id), 0) AS customer_count,
                COALESCE((
                    SELECT SUM(value) FROM opportunities o
                    WHERE o.owner_user_id = u.id
                    AND o.stage = 'Kazanıldı'
                    AND date(o.closed_at) >= date('now', 'start of month')
                ), 0) AS monthly_sales
            FROM users u
                ORDER BY
                CASE u.role
                    WHEN 'Süper Admin' THEN 1
                    WHEN 'Yönetici' THEN 2
                    WHEN 'Satış Müdürü' THEN 3
                    WHEN 'Satış Temsilcisi' THEN 4
                    WHEN 'Destek' THEN 5
                    WHEN 'Finans' THEN 6
                    ELSE 99
                END,
                u.full_name
            """
        )

    def save_user(self, payload: Dict[str, Any], user_id: Optional[int] = None, actor_id: Optional[int] = None) -> int:
        now = now_iso()
        password = payload.get("password", "")
        if payload.get("role") not in ROLE_OPTIONS:
            raise ValueError("Geçersiz kullanıcı rolü.")
        if user_id:
            current = self.get_user(user_id)
            if not current:
                raise ValueError("Kullanıcı bulunamadı.")
            password_hash = current["password_hash"]
            password_salt = current["password_salt"]
            if password:
                password_hash, password_salt = self.hash_password(password)
            self.execute(
                """
                UPDATE users
                SET full_name = ?, email = ?, phone = ?, role = ?, is_active = ?, password_hash = ?, password_salt = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["full_name"].strip(),
                    payload["email"].strip(),
                    payload.get("phone", "").strip(),
                    payload["role"],
                    1 if payload.get("is_active", True) else 0,
                    password_hash,
                    password_salt,
                    now,
                    user_id,
                ),
            )
            self.record_activity(
                "Kullanıcı",
                "user",
                user_id,
                f"{payload['full_name']} güncellendi",
                "Kullanıcı profili düzenlendi.",
                related_user_id=actor_id or user_id,
            )
            return user_id

        password_hash, password_salt = self.hash_password(password or "Admin123!")
        cursor = self.execute(
            """
            INSERT INTO users(full_name, email, phone, role, password_hash, password_salt, is_active, last_login, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                payload["full_name"].strip(),
                payload["email"].strip(),
                payload.get("phone", "").strip(),
                payload["role"],
                password_hash,
                password_salt,
                1 if payload.get("is_active", True) else 0,
                now,
                now,
            ),
        )
        new_id = int(cursor.lastrowid)
        self.record_activity(
            "Kullanıcı",
            "user",
            new_id,
            f"{payload['full_name']} eklendi",
            "Yeni ekip kullanıcısı oluşturuldu.",
            related_user_id=actor_id or new_id,
        )
        self.create_notification(
            "Yeni kullanıcı",
            f"{payload['full_name']} ekip listesine eklendi.",
            "Bilgi",
            "team",
            new_id,
        )
        return new_id

    def change_password(self, user_id: int, current_password: str, new_password: str) -> tuple[bool, str]:
        user = self.get_user(user_id)
        if not user:
            return False, "Kullanıcı bulunamadı."
        digest, _ = self.hash_password(current_password, user["password_salt"])
        if digest != user["password_hash"]:
            return False, "Mevcut şifre hatalı."
        new_hash, new_salt = self.hash_password(new_password)
        self.execute(
            "UPDATE users SET password_hash = ?, password_salt = ?, updated_at = ? WHERE id = ?",
            (new_hash, new_salt, now_iso(), user_id),
        )
        return True, "Şifre başarıyla güncellendi."

    def delete_user(self, user_id: int) -> tuple[bool, str]:
        """Kullanıcıyı veritabanından siler. İlgili kayıtlar NULL'a ayarlanır."""
        user = self.get_user(user_id)
        if not user:
            return False, "Kullanıcı bulunamadı."
        try:
            self.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.create_notification(
                "Kullanıcı silindi",
                f"{user['full_name']} ({user['role']}) sistem kullanıcılarından kaldırıldı.",
                "Uyarı",
            )
            return True, f"{user['full_name']} başarıyla silindi."
        except Exception as exc:
            return False, f"Silme işlemi başarısız oldu: {str(exc)}"

    def list_contacts(
        self,
        search: str = "",
        status: str = "",
        tag: str = "",
        priority: str = "",
        sort_by: str = "En Yeni",
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT
                c.*,
                u.full_name AS assigned_name,
                COALESCE((SELECT SUM(value) FROM opportunities o WHERE o.contact_id = c.id AND o.stage = 'Kazanıldı'), 0) AS total_sales,
                COALESCE((SELECT COUNT(*) FROM calls cl WHERE cl.contact_id = c.id), 0) AS calls_count,
                COALESCE((SELECT COUNT(*) FROM opportunities o2 WHERE o2.contact_id = c.id AND o2.stage NOT IN ('Kazanıldı', 'Kaybedildi')), 0) AS open_opportunities
            FROM contacts c
            LEFT JOIN users u ON u.id = c.assigned_user_id
            WHERE 1 = 1
        """
        params: List[Any] = []
        if search:
            like = f"%{search.strip()}%"
            query += " AND (c.full_name LIKE ? OR c.company LIKE ? OR c.email LIKE ? OR c.phone LIKE ?)"
            params.extend([like, like, like, like])
        if status:
            query += " AND c.status = ?"
            params.append(status)
        if tag:
            query += " AND c.tag = ?"
            params.append(tag)
        if priority:
            query += " AND c.priority = ?"
            params.append(priority)

        order_map = {
            "En Yeni": "datetime(c.created_at) DESC",
            "A-Z": "c.full_name COLLATE NOCASE ASC",
            "En Yüksek Satış": "total_sales DESC, c.ai_score DESC",
            "AI Skor": "c.ai_score DESC, datetime(c.updated_at) DESC",
        }
        query += f" ORDER BY {order_map.get(sort_by, order_map['En Yeni'])}"
        return self.fetchall(query, params)

    def get_contact(self, contact_id: int) -> Optional[Dict[str, Any]]:
        contact = self.fetchone(
            """
            SELECT
                c.*,
                u.full_name AS assigned_name,
                COALESCE((SELECT SUM(value) FROM opportunities o WHERE o.contact_id = c.id AND o.stage = 'Kazanıldı'), 0) AS total_sales,
                COALESCE((SELECT COUNT(*) FROM calls cl WHERE cl.contact_id = c.id), 0) AS calls_count,
                COALESCE((SELECT COUNT(*) FROM opportunities o2 WHERE o2.contact_id = c.id AND o2.stage NOT IN ('Kazanıldı', 'Kaybedildi')), 0) AS open_opportunities
            FROM contacts c
            LEFT JOIN users u ON u.id = c.assigned_user_id
            WHERE c.id = ?
            """,
            (contact_id,),
        )
        return contact

    def save_contact(self, payload: Dict[str, Any], contact_id: Optional[int] = None, actor_id: Optional[int] = None) -> int:
        now = now_iso()
        payment = safe_int(payload.get("payment_score", 70), 70)
        potential = safe_int(payload.get("potential_score", 70), 70)
        loyalty = safe_int(payload.get("loyalty_score", 70), 70)
        churn = safe_int(payload.get("churn_risk", 20), 20)
        ai_score = self.compute_ai_score(payment, potential, loyalty, churn)
        values = (
            payload["full_name"].strip(),
            payload["company"].strip(),
            payload.get("title", "").strip(),
            payload.get("phone", "").strip(),
            payload.get("whatsapp", "").strip(),
            payload.get("email", "").strip(),
            payload.get("city", "").strip(),
            payload.get("country", "Türkiye").strip(),
            payload["status"],
            payload["priority"],
            payload["tag"],
            payload.get("notes", "").strip(),
            payload.get("assigned_user_id"),
            payment,
            potential,
            loyalty,
            churn,
            ai_score,
            payload.get("last_contact_at"),
            payload.get("reminder_at"),
        )
        if contact_id:
            self.execute(
                """
                UPDATE contacts
                SET full_name = ?, company = ?, title = ?, phone = ?, whatsapp = ?, email = ?, city = ?, country = ?,
                    status = ?, priority = ?, tag = ?, notes = ?, assigned_user_id = ?, payment_score = ?, potential_score = ?,
                    loyalty_score = ?, churn_risk = ?, ai_score = ?, last_contact_at = ?, reminder_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (*values, now, contact_id),
            )
            self.record_activity(
                "Müşteri",
                "contact",
                contact_id,
                f"{payload['full_name']} güncellendi",
                f"{payload['company']} müşterisinin kartı güncellendi.",
                related_contact_id=contact_id,
                related_user_id=actor_id or payload.get("assigned_user_id"),
            )
            return contact_id

        cursor = self.execute(
            """
            INSERT INTO contacts(
                full_name, company, title, phone, whatsapp, email, city, country, status, priority, tag, notes,
                assigned_user_id, payment_score, potential_score, loyalty_score, churn_risk, ai_score,
                last_contact_at, reminder_at, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*values, now, now),
        )
        new_id = int(cursor.lastrowid)
        self.record_activity(
            "Müşteri",
            "contact",
            new_id,
            f"{payload['full_name']} eklendi",
            f"{payload['company']} için yeni müşteri kaydı oluşturuldu.",
            related_contact_id=new_id,
            related_user_id=actor_id or payload.get("assigned_user_id"),
        )
        self.create_notification(
            "Yeni müşteri",
            f"{payload['full_name']} müşteri listesine eklendi.",
            "Bilgi",
            "contacts",
            new_id,
        )
        return new_id

    def delete_contact(self, contact_id: int) -> None:
        contact = self.get_contact(contact_id)
        if not contact:
            return
        self.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        self.create_notification(
            "Müşteri silindi",
            f"{contact['full_name']} kaydı arşivden kaldırıldı.",
            "Uyarı",
            "contacts",
        )

    def add_contact_note(self, contact_id: int, author_user_id: Optional[int], title: str, content: str) -> int:
        timestamp = now_iso()
        cursor = self.execute(
            "INSERT INTO notes(contact_id, author_user_id, title, content, created_at) VALUES(?, ?, ?, ?, ?)",
            (contact_id, author_user_id, title.strip(), content.strip(), timestamp),
        )
        note_id = int(cursor.lastrowid)
        self.record_activity(
            "Not",
            "note",
            note_id,
            title.strip(),
            content.strip(),
            related_contact_id=contact_id,
            related_user_id=author_user_id,
        )
        return note_id

    def list_contact_notes(self, contact_id: int) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT n.*, u.full_name AS author_name
            FROM notes n
            LEFT JOIN users u ON u.id = n.author_user_id
            WHERE n.contact_id = ?
            ORDER BY datetime(n.created_at) DESC
            """,
            (contact_id,),
        )

    def list_opportunities(self, stage: str = "") -> List[Dict[str, Any]]:
        query = """
            SELECT
                o.*,
                c.full_name AS contact_name,
                c.company AS contact_company,
                c.ai_score AS contact_ai_score,
                u.full_name AS owner_name
            FROM opportunities o
            LEFT JOIN contacts c ON c.id = o.contact_id
            LEFT JOIN users u ON u.id = o.owner_user_id
            WHERE 1 = 1
        """
        params: List[Any] = []
        if stage:
            query += " AND o.stage = ?"
            params.append(stage)
        query += """
            ORDER BY
                CASE o.stage
                    WHEN 'Potansiyel' THEN 1
                    WHEN 'Görüşme' THEN 2
                    WHEN 'Teklif' THEN 3
                    WHEN 'Kazanıldı' THEN 4
                    ELSE 5
                END,
                o.value DESC
        """
        return self.fetchall(query, params)

    def get_opportunity(self, opportunity_id: int) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            """
            SELECT o.*, c.full_name AS contact_name, c.company AS contact_company, u.full_name AS owner_name
            FROM opportunities o
            LEFT JOIN contacts c ON c.id = o.contact_id
            LEFT JOIN users u ON u.id = o.owner_user_id
            WHERE o.id = ?
            """,
            (opportunity_id,),
        )

    def save_opportunity(self, payload: Dict[str, Any], opportunity_id: Optional[int] = None, actor_id: Optional[int] = None) -> int:
        now = now_iso()
        stage = payload["stage"]
        probability = safe_int(payload.get("probability")) or self.probability_for_stage(stage)
        closed_at = now if stage == "Kazanıldı" else None
        values = (
            payload["contact_id"],
            payload["title"].strip(),
            stage,
            float(payload.get("value", 0) or 0),
            probability,
            payload.get("expected_close"),
            payload.get("notes", "").strip(),
            payload.get("owner_user_id"),
        )
        if opportunity_id:
            previous = self.get_opportunity(opportunity_id)
            if previous and previous["stage"] == "Kazanıldı" and stage != "Kazanıldı":
                closed_at = None
            elif previous and previous["stage"] != "Kazanıldı" and stage == "Kazanıldı":
                closed_at = now
            else:
                closed_at = previous["closed_at"] if previous else closed_at

            self.execute(
                """
                UPDATE opportunities
                SET contact_id = ?, title = ?, stage = ?, value = ?, probability = ?, expected_close = ?, notes = ?,
                    owner_user_id = ?, updated_at = ?, closed_at = ?
                WHERE id = ?
                """,
                (*values, now, closed_at, opportunity_id),
            )
            title = "Fırsat güncellendi"
            desc = f"{payload['title']} fırsatı {stage} aşamasına taşındı."
            entity_id = opportunity_id
        else:
            cursor = self.execute(
                """
                INSERT INTO opportunities(
                    contact_id, title, stage, value, probability, expected_close, notes, owner_user_id, created_at, updated_at, closed_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*values, now, now, closed_at),
            )
            entity_id = int(cursor.lastrowid)
            title = "Yeni fırsat"
            desc = f"{payload['title']} pipeline'a eklendi."

        contact = self.get_contact(payload["contact_id"])
        self.record_activity(
            "Fırsat",
            "opportunity",
            entity_id,
            title,
            desc,
            related_contact_id=payload["contact_id"],
            related_user_id=actor_id or payload.get("owner_user_id"),
        )
        if stage == "Kazanıldı" and contact:
            self.create_notification(
                "Satış kapandı",
                f"{contact['company']} için {payload['title']} başarıyla kazanıldı.",
                "Başarı",
                "pipeline",
                entity_id,
            )
        return entity_id

    def move_opportunity(self, opportunity_id: int, direction: int) -> None:
        opportunity = self.get_opportunity(opportunity_id)
        if not opportunity:
            return
        try:
            index = STAGE_ORDER.index(opportunity["stage"])
        except ValueError:
            index = 0
        new_index = min(max(index + direction, 0), len(STAGE_ORDER) - 1)
        new_stage = STAGE_ORDER[new_index]
        self.save_opportunity(
            {
                "contact_id": opportunity["contact_id"],
                "title": opportunity["title"],
                "stage": new_stage,
                "value": opportunity["value"],
                "probability": self.probability_for_stage(new_stage),
                "expected_close": opportunity["expected_close"],
                "notes": opportunity["notes"],
                "owner_user_id": opportunity["owner_user_id"],
            },
            opportunity_id=opportunity_id,
            actor_id=opportunity["owner_user_id"],
        )

    def delete_opportunity(self, opportunity_id: int) -> None:
        self.execute("DELETE FROM opportunities WHERE id = ?", (opportunity_id,))

    def list_calls(self, contact_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT
                cl.*,
                c.full_name AS contact_name,
                c.company AS contact_company,
                u.full_name AS owner_name
            FROM calls cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            LEFT JOIN users u ON u.id = cl.owner_user_id
            WHERE 1 = 1
        """
        params: List[Any] = []
        if contact_id:
            query += " AND cl.contact_id = ?"
            params.append(contact_id)
        query += " ORDER BY datetime(cl.scheduled_at) DESC"
        return self.fetchall(query, params)

    def get_call(self, call_id: int) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            """
            SELECT cl.*, c.full_name AS contact_name, c.company AS contact_company
            FROM calls cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            WHERE cl.id = ?
            """,
            (call_id,),
        )

    def save_call(self, payload: Dict[str, Any], call_id: Optional[int] = None, actor_id: Optional[int] = None) -> int:
        now = now_iso()
        values = (
            payload["contact_id"],
            payload["call_type"],
            payload["scheduled_at"],
            safe_int(payload.get("duration_minutes", 30), 30),
            payload["outcome"],
            payload.get("notes", "").strip(),
            payload.get("reminder_at"),
            payload.get("owner_user_id"),
        )
        if call_id:
            self.execute(
                """
                UPDATE calls
                SET contact_id = ?, call_type = ?, scheduled_at = ?, duration_minutes = ?, outcome = ?, notes = ?,
                    reminder_at = ?, owner_user_id = ?
                WHERE id = ?
                """,
                (*values, call_id),
            )
            new_id = call_id
        else:
            cursor = self.execute(
                """
                INSERT INTO calls(contact_id, call_type, scheduled_at, duration_minutes, outcome, notes, reminder_at, owner_user_id, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*values, now),
            )
            new_id = int(cursor.lastrowid)

        contact = self.get_contact(payload["contact_id"])
        contact_name = contact["full_name"] if contact else "Müşteri"
        self.record_activity(
            "Görüşme",
            "call",
            new_id,
            f"{contact_name} için görüşme planlandı",
            f"{payload['call_type']} tipi görüşme kaydı oluşturuldu.",
            related_contact_id=payload["contact_id"],
            related_user_id=actor_id or payload.get("owner_user_id"),
        )
        self.create_notification(
            "Yeni görüşme",
            f"{contact_name} için {payload['call_type'].lower()} planlandı.",
            "Bilgi",
            "calls",
            new_id,
        )
        return new_id

    def delete_call(self, call_id: int) -> None:
        self.execute("DELETE FROM calls WHERE id = ?", (call_id,))

    def list_tasks(self, include_done: bool = True) -> List[Dict[str, Any]]:
        query = """
            SELECT
                t.*,
                u.full_name AS assigned_name,
                c.full_name AS contact_name
            FROM tasks t
            LEFT JOIN users u ON u.id = t.assigned_user_id
            LEFT JOIN contacts c ON c.id = t.contact_id
        """
        if not include_done:
            query += " WHERE t.is_done = 0"
        query += """
            ORDER BY
                t.is_done ASC,
                CASE
                    WHEN t.is_done = 0 AND t.due_at IS NOT NULL AND datetime(t.due_at) < datetime('now') THEN 0
                    ELSE 1
                END,
                CASE t.priority WHEN 'Yüksek' THEN 1 WHEN 'Orta' THEN 2 ELSE 3 END,
                COALESCE(datetime(t.due_at), datetime(t.created_at)) ASC
        """
        return self.fetchall(query)

    def save_task(self, payload: Dict[str, Any], task_id: Optional[int] = None, actor_id: Optional[int] = None) -> int:
        now = now_iso()
        is_done = 1 if payload.get("is_done") else 0
        status = "Tamamlandı" if is_done else payload.get("status", "Bekliyor")
        completed_at = now if is_done else None
        values = (
            payload["title"].strip(),
            payload.get("description", "").strip(),
            payload["priority"],
            payload.get("due_at"),
            status,
            is_done,
            completed_at,
            payload.get("assigned_user_id"),
            payload.get("contact_id"),
            payload.get("owner_user_id"),
            now,
        )
        if task_id:
            self.execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, priority = ?, due_at = ?, status = ?, is_done = ?, completed_at = ?,
                    assigned_user_id = ?, contact_id = ?, owner_user_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (*values, task_id),
            )
            new_id = task_id
        else:
            cursor = self.execute(
                """
                INSERT INTO tasks(title, description, priority, due_at, status, is_done, completed_at, assigned_user_id, contact_id, owner_user_id, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*values[:-1], now, now),
            )
            new_id = int(cursor.lastrowid)

        self.record_activity(
            "Görev",
            "task",
            new_id,
            payload["title"].strip(),
            "Görev kaydı güncellendi.",
            related_contact_id=payload.get("contact_id"),
            related_user_id=actor_id or payload.get("assigned_user_id"),
        )
        return new_id

    def toggle_task(self, task_id: int) -> None:
        task = self.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not task:
            return
        is_done = 0 if task["is_done"] else 1
        status = "Tamamlandı" if is_done else "Bekliyor"
        completed_at = now_iso() if is_done else None
        self.execute(
            "UPDATE tasks SET is_done = ?, status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            (is_done, status, completed_at, now_iso(), task_id),
        )

    def delete_task(self, task_id: int) -> None:
        self.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def list_emails(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT
                e.*,
                c.full_name AS contact_name,
                c.company AS contact_company,
                u.full_name AS created_by_name
            FROM emails e
            LEFT JOIN contacts c ON c.id = e.contact_id
            LEFT JOIN users u ON u.id = e.created_by
            ORDER BY e.is_unread DESC, datetime(COALESCE(e.sent_at, e.created_at)) DESC
            """
        )

    def get_email(self, email_id: int) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            """
            SELECT e.*, c.full_name AS contact_name
            FROM emails e
            LEFT JOIN contacts c ON c.id = e.contact_id
            WHERE e.id = ?
            """,
            (email_id,),
        )

    def mark_email_read(self, email_id: int) -> None:
        self.execute("UPDATE emails SET is_unread = 0 WHERE id = ?", (email_id,))

    def save_email(self, payload: Dict[str, Any], actor_id: Optional[int] = None) -> int:
        timestamp = now_iso()
        status = payload.get("status", "Gönderildi")
        sent_at = timestamp if status == "Gönderildi" else None
        cursor = self.execute(
            """
            INSERT INTO emails(contact_id, recipient, subject, body, template_name, status, direction, is_unread, sent_at, created_by, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("contact_id"),
                payload["recipient"].strip(),
                payload["subject"].strip(),
                payload["body"].strip(),
                payload.get("template_name"),
                status,
                payload.get("direction", "Giden"),
                1 if payload.get("is_unread") else 0,
                sent_at,
                actor_id or payload.get("created_by"),
                timestamp,
            ),
        )
        email_id = int(cursor.lastrowid)
        self.record_activity(
            "Mail",
            "email",
            email_id,
            payload["subject"].strip(),
            f"{payload['recipient']} adresine mail kaydı oluşturuldu.",
            related_contact_id=payload.get("contact_id"),
            related_user_id=actor_id or payload.get("created_by"),
        )
        return email_id

    def upload_file(
        self,
        source_path: str,
        contact_id: Optional[int],
        category: str,
        notes: str = "",
        uploaded_by: Optional[int] = None,
    ) -> int:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError("Seçilen dosya bulunamadı.")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        stored_name = f"{timestamp}_{source.name}"
        destination = self.upload_dir / stored_name
        shutil.copy2(str(source), str(destination))
        cursor = self.execute(
            """
            INSERT INTO files(contact_id, original_name, stored_name, category, mime_type, size_bytes, notes, uploaded_by, uploaded_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contact_id,
                source.name,
                stored_name,
                category,
                source.suffix.lower(),
                source.stat().st_size,
                notes.strip(),
                uploaded_by,
                now_iso(),
            ),
        )
        file_id = int(cursor.lastrowid)
        self.record_activity(
            "Dosya",
            "file",
            file_id,
            source.name,
            "Yeni dosya yüklendi.",
            related_contact_id=contact_id,
            related_user_id=uploaded_by,
        )
        return file_id

    def list_files(self, search: str = "", category: str = "", contact_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT f.*, c.full_name AS contact_name, c.company AS contact_company, u.full_name AS uploader_name
            FROM files f
            LEFT JOIN contacts c ON c.id = f.contact_id
            LEFT JOIN users u ON u.id = f.uploaded_by
            WHERE 1 = 1
        """
        params: List[Any] = []
        if search:
            like = f"%{search.strip()}%"
            query += " AND (f.original_name LIKE ? OR COALESCE(c.full_name, '') LIKE ? OR COALESCE(c.company, '') LIKE ?)"
            params.extend([like, like, like])
        if category:
            query += " AND f.category = ?"
            params.append(category)
        if contact_id:
            query += " AND f.contact_id = ?"
            params.append(contact_id)
        query += " ORDER BY datetime(f.uploaded_at) DESC"
        return self.fetchall(query, params)

    def get_file(self, file_id: int) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM files WHERE id = ?", (file_id,))

    def get_file_path(self, file_id: int) -> Optional[Path]:
        file_row = self.get_file(file_id)
        if not file_row:
            return None
        path = self.upload_dir / file_row["stored_name"]
        return path if path.exists() else None

    def delete_file(self, file_id: int) -> None:
        file_row = self.get_file(file_id)
        if not file_row:
            return
        path = self.upload_dir / file_row["stored_name"]
        if path.exists():
            path.unlink()
        self.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def global_search(self, term: str) -> Dict[str, List[Dict[str, Any]]]:
        like = f"%{term.strip()}%"
        return {
            "contacts": self.fetchall(
                "SELECT id, full_name, company, 'contact' AS kind FROM contacts WHERE full_name LIKE ? OR company LIKE ? LIMIT 6",
                (like, like),
            ),
            "opportunities": self.fetchall(
                "SELECT id, title, stage AS company, 'opportunity' AS kind FROM opportunities WHERE title LIKE ? LIMIT 6",
                (like,),
            ),
            "tasks": self.fetchall(
                "SELECT id, title AS full_name, status AS company, 'task' AS kind FROM tasks WHERE title LIKE ? LIMIT 6",
                (like,),
            ),
            "files": self.fetchall(
                "SELECT id, original_name AS full_name, category AS company, 'file' AS kind FROM files WHERE original_name LIKE ? LIMIT 6",
                (like,),
            ),
        }

    def ensure_runtime_notifications(self) -> None:
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        upcoming_calls = self.fetchall(
            """
            SELECT cl.id, c.full_name AS contact_name, cl.scheduled_at
            FROM calls cl
            JOIN contacts c ON c.id = cl.contact_id
            WHERE datetime(cl.scheduled_at) BETWEEN datetime(?) AND datetime(?)
            """,
            (now.isoformat(), tomorrow.isoformat()),
        )
        for call in upcoming_calls:
            scheduled = parse_iso(call["scheduled_at"])
            when_text = (
                f"{scheduled.day:02d} {MONTH_LABELS[scheduled.month - 1]} {scheduled.hour:02d}:{scheduled.minute:02d}"
                if scheduled
                else "yakında"
            )
            self.create_notification(
                "Yaklaşan görüşme",
                f"{call['contact_name']} ile görüşme {when_text} tarihinde.",
                "Uyarı",
                "calls",
                call["id"],
                dedupe_key=f"call:{call['id']}",
            )

        risk_contacts = self.fetchall(
            "SELECT id, full_name FROM contacts WHERE ai_score <= 50 OR churn_risk >= 60 ORDER BY churn_risk DESC LIMIT 3"
        )
        for contact in risk_contacts:
            self.create_notification(
                "Risk uyarısı",
                f"{contact['full_name']} için müşteri riski yükseldi.",
                "Kritik",
                "contacts",
                contact["id"],
                dedupe_key=f"risk:{contact['id']}",
            )

    def get_dashboard_summary(self) -> Dict[str, Any]:
        contacts = self.list_contacts(sort_by="AI Skor")
        opportunities = self.list_opportunities()
        calls = self.list_calls()
        tasks = self.list_tasks()
        now = datetime.now()
        today = now.date()
        month_start = first_day_of_month(today)
        next_month = add_months(month_start, 1)

        monthly_sales = sum(
            opp["value"]
            for opp in opportunities
            if opp["stage"] == "Kazanıldı"
            and parse_iso(opp["closed_at"])
            and month_start <= parse_iso(opp["closed_at"]).date() < next_month
        )
        previous_month_start = add_months(month_start, -1)
        previous_month_end = month_start
        previous_month_sales = sum(
            opp["value"]
            for opp in opportunities
            if opp["stage"] == "Kazanıldı"
            and parse_iso(opp["closed_at"])
            and previous_month_start <= parse_iso(opp["closed_at"]).date() < previous_month_end
        )
        growth = 0
        if previous_month_sales > 0:
            growth = round(((monthly_sales - previous_month_sales) / previous_month_sales) * 100)

        open_pipeline = [opp for opp in opportunities if opp["stage"] not in ("Kazanıldı", "Kaybedildi")]
        pending_offers = [opp for opp in opportunities if opp["stage"] == "Teklif"]
        upcoming_calls = [call for call in calls if parse_iso(call["scheduled_at"]) and parse_iso(call["scheduled_at"]) >= now]
        today_calls = [call for call in upcoming_calls if parse_iso(call["scheduled_at"]).date() == today]
        active_tasks = [task for task in tasks if not task["is_done"]]
        top_customer = contacts[0] if contacts else None
        risky_accounts = sorted(
            [item for item in contacts if item["ai_score"] <= 55 or item["churn_risk"] >= 50],
            key=lambda item: (item["ai_score"], -item["churn_risk"]),
        )
        risk_customers = risky_accounts[:5]

        sales_series = self.get_sales_series()

        return {
            "total_customers": len(contacts),
            "monthly_sales": monthly_sales,
            "growth": growth,
            "pending_offer_count": len(pending_offers),
            "pending_offer_value": sum(opp["value"] for opp in pending_offers),
            "upcoming_call_count": len(upcoming_calls),
            "today_call_count": len(today_calls),
            "pipeline_value": sum(opp["value"] for opp in open_pipeline),
            "top_customer": top_customer,
            "risk_customers": risk_customers,
            "risk_customer_count": len(risky_accounts),
            "recent_activities": self.list_activities(limit=6),
            "top_customers": sorted(contacts, key=lambda item: item["total_sales"], reverse=True)[:5],
            "upcoming_tasks": active_tasks[:5],
            "goal_sales_percent": min(100, int(round((monthly_sales / 200000) * 100))) if monthly_sales else 0,
            "goal_customer_percent": min(100, int(round((len(contacts) / 15) * 100))),
            "goal_calls_percent": min(100, int(round((len(calls) / 12) * 100))),
            "goal_close_percent": min(100, int(round((len([o for o in opportunities if o['stage'] == 'Kazanıldı']) / max(len(opportunities), 1)) * 100))),
            "sales_series": sales_series,
        }

    def get_pipeline_summary(self) -> List[Dict[str, Any]]:
        stages: List[Dict[str, Any]] = []
        colors = {
            "Potansiyel": "#94a3b8",
            "Görüşme": "#2563eb",
            "Teklif": "#d97706",
            "Kazanıldı": "#059669",
            "Kaybedildi": "#e11d48",
        }
        opportunities = self.list_opportunities()
        for stage in STAGE_ORDER:
            stage_items = [item for item in opportunities if item["stage"] == stage]
            stages.append(
                {
                    "stage": stage,
                    "color": colors.get(stage, "#64748b"),
                    "count": len(stage_items),
                    "value": sum(item["value"] for item in stage_items),
                    "items": stage_items,
                }
            )
        return stages

    def get_calls_summary(self) -> Dict[str, Any]:
        calls = self.list_calls()
        upcoming = [call for call in calls if parse_iso(call["scheduled_at"]) and parse_iso(call["scheduled_at"]) >= datetime.now()]
        return {
            "upcoming": sorted(upcoming, key=lambda item: item["scheduled_at"])[:5],
        }

    def get_calendar_events(self, month: int, year: int) -> List[Dict[str, Any]]:
        start = datetime(year, month, 1)
        end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        calls = self.fetchall(
            """
            SELECT cl.id, cl.call_type AS kind, cl.scheduled_at AS event_at, c.full_name AS title
            FROM calls cl
            LEFT JOIN contacts c ON c.id = cl.contact_id
            WHERE datetime(cl.scheduled_at) BETWEEN datetime(?) AND datetime(?)
            """,
            (start.isoformat(), end.isoformat()),
        )
        tasks = self.fetchall(
            """
            SELECT t.id, 'Görev' AS kind, t.due_at AS event_at, t.title
            FROM tasks t
            WHERE t.due_at IS NOT NULL
            AND datetime(t.due_at) BETWEEN datetime(?) AND datetime(?)
            """,
            (start.isoformat(), end.isoformat()),
        )
        return sorted(calls + tasks, key=lambda item: item["event_at"])

    def get_sales_series(self, months: int = 12) -> Dict[str, List[Any]]:
        current = first_day_of_month(date.today())
        labels: List[str] = []
        values: List[float] = []
        for offset in range(months - 1, -1, -1):
            start = add_months(current, -offset)
            end = add_months(start, 1)
            labels.append(MONTH_LABELS[start.month - 1])
            row = self.fetchone(
                """
                SELECT COALESCE(SUM(value), 0) AS total
                FROM opportunities
                WHERE stage = 'Kazanıldı'
                AND closed_at IS NOT NULL
                AND date(closed_at) >= date(?)
                AND date(closed_at) < date(?)
                """,
                (start.isoformat(), end.isoformat()),
            )
            values.append(float(row["total"] if row else 0))
        return {"labels": labels, "values": values}

    def get_reports_summary(self) -> Dict[str, Any]:
        opportunities = self.list_opportunities()
        contacts = self.list_contacts()
        calls = self.list_calls()
        tasks = self.list_tasks(include_done=True)
        dashboard = self.get_dashboard_summary()
        pipeline = self.get_pipeline_summary()
        team = self.get_team_performance()

        won = [opp for opp in opportunities if opp["stage"] == "Kazanıldı"]
        lost = [opp for opp in opportunities if opp["stage"] == "Kaybedildi"]
        offers = [opp for opp in opportunities if opp["stage"] == "Teklif"]
        risky_contacts = sorted(
            [item for item in contacts if item["ai_score"] <= 55 or item["churn_risk"] >= 50],
            key=lambda item: (item["ai_score"], -item["churn_risk"]),
        )
        positive_calls = [call for call in calls if call["outcome"] == "Olumlu"]
        active_tasks = [task for task in tasks if not task["is_done"]]
        completed_tasks = [task for task in tasks if task["is_done"]]
        overdue_tasks = [
            task for task in active_tasks
            if task.get("due_at") and parse_iso(task["due_at"]) and parse_iso(task["due_at"]) < datetime.now()
        ]

        stage_colors = {
            "Potansiyel": "#94a3b8",
            "Görüşme": "#2563eb",
            "Teklif": "#d97706",
            "Kazanıldı": "#059669",
            "Kaybedildi": "#e11d48",
        }
        total_stage_count = max(len(opportunities), 1)
        stage_breakdown = [
            {
                "stage": item["stage"],
                "count": item["count"],
                "value": item["value"],
                "share": int(round((item["count"] / total_stage_count) * 100)),
                "color": stage_colors.get(item["stage"], "#64748b"),
            }
            for item in pipeline
        ]

        average_order = (sum(item["value"] for item in won) / len(won)) if won else 0
        task_completion_rate = int(round((len(completed_tasks) / max(len(tasks), 1)) * 100)) if tasks else 0

        return {
            "total_sales": dashboard["monthly_sales"],
            "pipeline_value": dashboard["pipeline_value"],
            "new_customers": len([c for c in contacts if parse_iso(c["created_at"]) and parse_iso(c["created_at"]).date() >= first_day_of_month(date.today())]),
            "close_rate": int(round((len(won) / max(len(opportunities), 1)) * 100)),
            "average_order": average_order,
            "sales_series": self.get_sales_series(),
            "team_performance": team,
            "call_total": len(calls),
            "call_positive_rate": int(round((len(positive_calls) / max(len(calls), 1)) * 100)) if calls else 0,
            "offer_count": len(offers),
            "offer_value": sum(item["value"] for item in offers),
            "won_count": len(won),
            "lost_count": len(lost),
            "active_task_count": len(active_tasks),
            "completed_task_count": len(completed_tasks),
            "task_total": len(tasks),
            "task_completion_rate": task_completion_rate,
            "overdue_task_count": len(overdue_tasks),
            "upcoming_call_count": dashboard["upcoming_call_count"],
            "risk_customer_count": len(risky_contacts),
            "top_accounts": sorted(
                contacts,
                key=lambda item: (item["total_sales"], item["ai_score"], item["open_opportunities"]),
                reverse=True,
            )[:5],
            "risk_accounts": risky_contacts[:3],
            "stage_breakdown": stage_breakdown,
            "monthly_growth": dashboard["growth"],
            "goal_progress": dashboard["goal_sales_percent"],
        }

    def get_team_performance(self) -> List[Dict[str, Any]]:
        team = self.list_users()
        for user in team:
            goal = ROLE_GOALS.get(user["role"], 50000)
            user["performance_percent"] = min(100, int(round((float(user["monthly_sales"]) / goal) * 100))) if goal else 0
            user["online_status"] = "Çevrimiçi" if user["last_login"] and parse_iso(user["last_login"]) and parse_iso(user["last_login"]) >= datetime.now() - timedelta(hours=12) else "Çevrimdışı"
        return team

    def get_ai_segments(self) -> Dict[str, Any]:
        contacts = self.list_contacts()
        high_potential = [item for item in contacts if item["potential_score"] >= 80 and item["churn_risk"] <= 30]
        growth = [item for item in contacts if item["ai_score"] >= 65 and item["potential_score"] >= 70]
        passive = [item for item in contacts if item["last_contact_at"] and parse_iso(item["last_contact_at"]) and parse_iso(item["last_contact_at"]) < datetime.now() - timedelta(days=30)]
        risky = [item for item in contacts if item["ai_score"] <= 55 or item["churn_risk"] >= 50]
        return {
            "high_potential": high_potential,
            "growth": growth,
            "passive": passive,
            "risky": risky,
        }

    def seed_defaults(self) -> None:
        if self.fetchone("SELECT id FROM users LIMIT 1"):
            return

        now = datetime.now()
        users = [
            {"full_name": "Admin Yönetici", "email": "admin@nexcrm.com", "phone": "0532 100 00 00", "role": "Süper Admin", "password": "Admin123!"},
            {"full_name": "Kaan Erdem", "email": "kaan@nexcrm.com", "phone": "0533 210 00 00", "role": "Yönetici", "password": "Kaan123!"},
            {"full_name": "Mert Aksoy", "email": "mert@nexcrm.com", "phone": "0534 220 00 00", "role": "Satış Müdürü", "password": "Mert123!"},
            {"full_name": "Zeynep Doğan", "email": "zeynep@nexcrm.com", "phone": "0534 310 00 00", "role": "Satış Temsilcisi", "password": "Zeynep123!"},
            {"full_name": "Elif Kara", "email": "elif@nexcrm.com", "phone": "0535 410 00 00", "role": "Destek", "password": "Elif123!"},
            {"full_name": "Deniz Şahin", "email": "deniz@nexcrm.com", "phone": "0536 510 00 00", "role": "Finans", "password": "Deniz123!"},
        ]
        user_ids: Dict[str, int] = {}
        for user in users:
            user_ids[user["full_name"]] = self.save_user(user)

        templates = [
            ("Takip Maili", "Görüşme Sonrası Takip", "Merhaba {{ad}},\n\nBugünkü görüşmemiz için teşekkür ederim. Konuştuğumuz başlıkların özetini paylaşmak ve bir sonraki adımları netleştirmek istiyorum.\n\nUygun olduğunuzda dönüşünüzü bekliyorum.\n\nSaygılarımla"),
            ("Teklif Gönderimi", "Teklif Dosyanız Hazır", "Merhaba {{ad}},\n\nTalebinize uygun teklif dosyanızı ekledim. Dilerseniz kısa bir toplantı ile maddeleri birlikte gözden geçirebiliriz.\n\nİyi çalışmalar."),
            ("Hoş Geldin", "NexCRM Ailesine Hoş Geldiniz", "Merhaba {{ad}},\n\nSizinle çalışacak olmaktan mutluluk duyuyoruz. İlk kurulum ve onboarding adımlarını planlamak için size yardımcı olacağız."),
            ("Hatırlatma", "Planlanan Aksiyon Hatırlatması", "Merhaba {{ad}},\n\nPlanladığımız aksiyon için size kısa bir hatırlatma iletmek istedim. Uygun olduğunuzda iletişime geçebiliriz."),
        ]
        self.executemany("INSERT INTO mail_templates(name, subject, body) VALUES(?, ?, ?)", templates)

        automations = [
            ("welcome_mail", "Hoş geldin maili", 1),
            ("follow_up_7d", "Takip hatırlatma (7 gün)", 1),
            ("birthday_mail", "Doğum günü tebrik", 0),
        ]
        self.executemany("INSERT INTO automations(key, label, enabled) VALUES(?, ?, ?)", automations)

        contacts = [
            {
                "full_name": "Ayşe Yılmaz",
                "company": "ABC Firma",
                "title": "Genel Müdür",
                "phone": "0532 123 45 67",
                "whatsapp": "05321234567",
                "email": "ayse@abcfirma.com",
                "city": "İstanbul",
                "country": "Türkiye",
                "status": "Aktif",
                "priority": "Yüksek",
                "tag": "VIP",
                "notes": "Demo sonrası premium teklif için sıcak müşteri.",
                "assigned_user_id": user_ids["Admin Yönetici"],
                "payment_score": 96,
                "potential_score": 88,
                "loyalty_score": 91,
                "churn_risk": 8,
                "last_contact_at": (now - timedelta(days=2)).replace(microsecond=0).isoformat(),
                "reminder_at": (now + timedelta(days=5)).replace(microsecond=0).isoformat(),
            },
            {
                "full_name": "Canan Demir",
                "company": "XYZ Ltd",
                "title": "Operasyon Direktörü",
                "phone": "0533 234 56 78",
                "whatsapp": "05332345678",
                "email": "canan@xyz.com",
                "city": "Ankara",
                "country": "Türkiye",
                "status": "Aktif",
                "priority": "Yüksek",
                "tag": "Enterprise",
                "notes": "Fiyat müzakeresi devam ediyor.",
                "assigned_user_id": user_ids["Kaan Erdem"],
                "payment_score": 89,
                "potential_score": 94,
                "loyalty_score": 82,
                "churn_risk": 18,
                "last_contact_at": (now - timedelta(days=4)).replace(microsecond=0).isoformat(),
                "reminder_at": (now + timedelta(days=1)).replace(microsecond=0).isoformat(),
            },
            {
                "full_name": "Mehmet Kaya",
                "company": "Delta AŞ",
                "title": "Satın Alma Müdürü",
                "phone": "0534 345 67 89",
                "whatsapp": "05343456789",
                "email": "mehmet@delta.com",
                "city": "Bursa",
                "country": "Türkiye",
                "status": "Beklemede",
                "priority": "Orta",
                "tag": "Potansiyel",
                "notes": "Bütçe konusu yüzünden beklemede.",
                "assigned_user_id": user_ids["Kaan Erdem"],
                "payment_score": 78,
                "potential_score": 74,
                "loyalty_score": 67,
                "churn_risk": 34,
                "last_contact_at": (now - timedelta(days=8)).replace(microsecond=0).isoformat(),
                "reminder_at": (now + timedelta(days=9)).replace(microsecond=0).isoformat(),
            },
            {
                "full_name": "Kadir Tekin",
                "company": "Kalite Koç",
                "title": "Kurucu",
                "phone": "0535 456 78 90",
                "whatsapp": "05354567890",
                "email": "kadir@kalitekoc.com",
                "city": "İzmir",
                "country": "Türkiye",
                "status": "Aktif",
                "priority": "Yüksek",
                "tag": "VIP",
                "notes": "Demo sonrası hızlı karar bekleniyor.",
                "assigned_user_id": user_ids["Admin Yönetici"],
                "payment_score": 87,
                "potential_score": 83,
                "loyalty_score": 79,
                "churn_risk": 21,
                "last_contact_at": (now - timedelta(days=1)).replace(microsecond=0).isoformat(),
                "reminder_at": (now + timedelta(days=3)).replace(microsecond=0).isoformat(),
            },
            {
                "full_name": "Sabri Can",
                "company": "Garfson AŞ",
                "title": "İş Geliştirme Müdürü",
                "phone": "0536 567 89 01",
                "whatsapp": "05365678901",
                "email": "sabri@garfson.com",
                "city": "Adana",
                "country": "Türkiye",
                "status": "Riskli",
                "priority": "Düşük",
                "tag": "Soğuk",
                "notes": "Rakip çözümü test ediyor, kurtarma kampanyası gerekli.",
                "assigned_user_id": user_ids["Zeynep Doğan"],
                "payment_score": 54,
                "potential_score": 52,
                "loyalty_score": 43,
                "churn_risk": 72,
                "last_contact_at": (now - timedelta(days=12)).replace(microsecond=0).isoformat(),
                "reminder_at": (now + timedelta(days=2)).replace(microsecond=0).isoformat(),
            },
            {
                "full_name": "Ferdin Tetlin",
                "company": "Tetlin Tech",
                "title": "CTO",
                "phone": "0537 678 90 12",
                "whatsapp": "05376789012",
                "email": "ferdin@tetlin.com",
                "city": "Eskişehir",
                "country": "Türkiye",
                "status": "Aktif",
                "priority": "Yüksek",
                "tag": "Potansiyel",
                "notes": "Bu hafta temas kurulursa kapanış şansı çok yüksek.",
                "assigned_user_id": user_ids["Admin Yönetici"],
                "payment_score": 93,
                "potential_score": 96,
                "loyalty_score": 80,
                "churn_risk": 12,
                "last_contact_at": (now - timedelta(days=5)).replace(microsecond=0).isoformat(),
                "reminder_at": (now + timedelta(days=1)).replace(microsecond=0).isoformat(),
            },
            {
                "full_name": "Meltem Kaya",
                "company": "MK Holding",
                "title": "Finans Direktörü",
                "phone": "0538 789 01 23",
                "whatsapp": "05387890123",
                "email": "meltem@mkhld.com",
                "city": "İstanbul",
                "country": "Türkiye",
                "status": "Aktif",
                "priority": "Orta",
                "tag": "Enterprise",
                "notes": "Finans ekibi teknik doğrulama bekliyor.",
                "assigned_user_id": user_ids["Zeynep Doğan"],
                "payment_score": 84,
                "potential_score": 77,
                "loyalty_score": 75,
                "churn_risk": 24,
                "last_contact_at": (now - timedelta(days=7)).replace(microsecond=0).isoformat(),
                "reminder_at": (now + timedelta(days=6)).replace(microsecond=0).isoformat(),
            },
        ]
        contact_ids: Dict[str, int] = {}
        for contact in contacts:
            contact_ids[contact["full_name"]] = self.save_contact(contact)

        won_values = [72000, 85000, 91000, 108000, 115000, 98000, 122000, 134000, 118000, 142000, 155800, 164500]
        contact_cycle = list(contact_ids.keys())
        owner_cycle = list(user_ids.values())
        for index, value in enumerate(won_values):
            month_start = add_months(first_day_of_month(date.today()), -(11 - index))
            closed_at = datetime(month_start.year, month_start.month, 18, 14, 0).isoformat()
            self.save_opportunity(
                {
                    "contact_id": contact_ids[contact_cycle[index % len(contact_cycle)]],
                    "title": f"Aylık satış paketi {index + 1}",
                    "stage": "Kazanıldı",
                    "value": value,
                    "probability": 100,
                    "expected_close": closed_at,
                    "notes": "Raporlar için seed satış kaydı.",
                    "owner_user_id": owner_cycle[index % len(owner_cycle)],
                }
            )
            self.execute("UPDATE opportunities SET closed_at = ?, created_at = ?, updated_at = ? WHERE title = ?", (closed_at, closed_at, closed_at, f"Aylık satış paketi {index + 1}"))

        live_opportunities = [
            ("Kurumsal Lisans Yenileme", "Ayşe Yılmaz", "Teklif", 45000, 91, 5),
            ("Premium Paket Genişleme", "Canan Demir", "Görüşme", 35000, 68, 8),
            ("Q2 Otomasyon Dönüşümü", "Kadir Tekin", "Görüşme", 22000, 72, 11),
            ("Finans Paneli Entegrasyonu", "Meltem Kaya", "Görüşme", 18000, 55, 16),
            ("Satış Operasyon Desteği", "Ferdin Tetlin", "Potansiyel", 19800, 84, 14),
            ("Teklif Revizyonu", "Mehmet Kaya", "Teklif", 27000, 63, 21),
            ("Rakipten Geri Kazanım", "Sabri Can", "Kaybedildi", 15000, 0, -10),
        ]
        for idx, (title, contact_name, stage, value, probability, day_delta) in enumerate(live_opportunities):
            expected = (now + timedelta(days=day_delta)).replace(microsecond=0).isoformat()
            self.save_opportunity(
                {
                    "contact_id": contact_ids[contact_name],
                    "title": title,
                    "stage": stage,
                    "value": value,
                    "probability": probability,
                    "expected_close": expected,
                    "notes": f"{contact_name} için aktif pipeline kaydı.",
                    "owner_user_id": owner_cycle[idx % len(owner_cycle)],
                }
            )

        calls = [
            {"contact": "Ayşe Yılmaz", "call_type": "Toplantı", "scheduled_at": now - timedelta(days=10, hours=2), "duration": 45, "outcome": "Olumlu", "notes": "Demo sunumu başarıyla tamamlandı."},
            {"contact": "Canan Demir", "call_type": "Telefon", "scheduled_at": now - timedelta(days=2, hours=3), "duration": 22, "outcome": "Beklemede", "notes": "Fiyat müzakeresi devam ediyor."},
            {"contact": "Mehmet Kaya", "call_type": "Toplantı", "scheduled_at": now - timedelta(days=5, hours=6), "duration": 60, "outcome": "Olumsuz", "notes": "Bütçe nedeniyle faz kaydı ertelendi."},
            {"contact": "Sabri Can", "call_type": "Telefon", "scheduled_at": now - timedelta(days=7, hours=1), "duration": 15, "outcome": "Riskli", "notes": "Rakip teklif değerlendirmesi yapıyor."},
            {"contact": "Canan Demir", "call_type": "Toplantı", "scheduled_at": now + timedelta(hours=4), "duration": 30, "outcome": "Beklemede", "notes": "Fiyat revizyon toplantısı."},
            {"contact": "Kadir Tekin", "call_type": "Toplantı", "scheduled_at": now + timedelta(days=1, hours=2), "duration": 40, "outcome": "Beklemede", "notes": "Demo sunumu ve teknik soru-cevap."},
        ]
        for idx, call in enumerate(calls):
            scheduled = call["scheduled_at"].replace(microsecond=0).isoformat()
            self.save_call(
                {
                    "contact_id": contact_ids[call["contact"]],
                    "call_type": call["call_type"],
                    "scheduled_at": scheduled,
                    "duration_minutes": call["duration"],
                    "outcome": call["outcome"],
                    "notes": call["notes"],
                    "reminder_at": (call["scheduled_at"] - timedelta(hours=2)).replace(microsecond=0).isoformat(),
                    "owner_user_id": owner_cycle[idx % len(owner_cycle)],
                }
            )

        tasks = [
            {"title": "ABC Firma teklifini finalize et", "priority": "Düşük", "due_at": now - timedelta(days=4), "is_done": True, "contact": "Ayşe Yılmaz"},
            {"title": "Canan Demir takip görüşmesi", "priority": "Yüksek", "due_at": now + timedelta(hours=6), "is_done": False, "contact": "Canan Demir"},
            {"title": "Q2 satış raporunu hazırla", "priority": "Orta", "due_at": now + timedelta(days=1, hours=4), "is_done": False, "contact": None},
            {"title": "Delta AŞ sunum taslağı", "priority": "Orta", "due_at": now + timedelta(days=3, hours=2), "is_done": False, "contact": "Mehmet Kaya"},
            {"title": "Yeni müşteri onboarding planı", "priority": "Düşük", "due_at": now + timedelta(days=4), "is_done": False, "contact": None},
            {"title": "Pipeline güncelleme toplantısı", "priority": "Orta", "due_at": now + timedelta(days=6), "is_done": False, "contact": None},
        ]
        for idx, task in enumerate(tasks):
            due_at = task["due_at"].replace(microsecond=0).isoformat()
            self.save_task(
                {
                    "title": task["title"],
                    "description": "Otomatik seed görevi",
                    "priority": task["priority"],
                    "due_at": due_at,
                    "status": "Tamamlandı" if task["is_done"] else "Bekliyor",
                    "is_done": task["is_done"],
                    "assigned_user_id": owner_cycle[idx % len(owner_cycle)],
                    "contact_id": contact_ids.get(task["contact"]) if task["contact"] else None,
                    "owner_user_id": owner_cycle[idx % len(owner_cycle)],
                }
            )

        notes = [
            ("Ayşe Yılmaz", "Demo Sonrası", "Demo çok iyi geçti. Premium paket önerilebilir, fiyatlandırma üzerinde orta seviye direnç var."),
            ("Ayşe Yılmaz", "Sözleşme Görüşmesi", "Hukuk ekibi revizyon maddelerini inceliyor. Bu ay kapanış bekleniyor."),
            ("Canan Demir", "Fiyat Müzakeresi", "İndirim yerine modüler paket ile ilerlemek daha doğru olabilir."),
            ("Sabri Can", "Risk Alarmı", "Rakip çözüme karşı yeniden konumlandırma yapılmalı."),
        ]
        for contact_name, title, content in notes:
            self.add_contact_note(contact_ids[contact_name], user_ids["Admin Yönetici"], title, content)

        inbound_mails = [
            ("Ayşe Yılmaz", "Teklif hakkında bilgi", "Merhaba, teklifinizi inceledim ve birkaç sorum var...", "Gelen", 1, now - timedelta(hours=5)),
            ("Canan Demir", "Toplantı onayı", "Yarınki toplantıyı onaylıyorum, görüşmek üzere.", "Gelen", 1, now - timedelta(hours=8)),
            ("Mehmet Kaya", "Re: Sözleşme revizyon", "Hukuk ekibimiz bazı maddelerde geri bildirim verdi.", "Gelen", 0, now - timedelta(days=1)),
        ]
        for contact_name, subject, body, direction, unread, mail_time in inbound_mails:
            self.save_email(
                {
                    "contact_id": contact_ids[contact_name],
                    "recipient": self.get_contact(contact_ids[contact_name])["email"],
                    "subject": subject,
                    "body": body,
                    "template_name": None,
                    "status": "Alındı",
                    "direction": direction,
                    "is_unread": unread,
                    "created_by": user_ids["Admin Yönetici"],
                }
            )
            self.execute(
                "UPDATE emails SET created_at = ?, sent_at = ? WHERE subject = ? AND direction = 'Gelen'",
                (mail_time.replace(microsecond=0).isoformat(), mail_time.replace(microsecond=0).isoformat(), subject),
            )

        sample_files = [
            ("Teklif_ABC_2026.txt", "Teklif", "Ayşe Yılmaz", "ABC Firma için teklif detayları."),
            ("Sozlesme_XYZ_v2.txt", "Belge", "Canan Demir", "XYZ Ltd sözleşme revizyon notları."),
            ("Q1_Rapor_2026.csv", "Rapor", None, "ay,gelir\nOcak,72000\nŞubat,85000\nMart,91000\n"),
        ]
        for filename, category, contact_name, content in sample_files:
            path = self.upload_dir / filename
            path.write_text(content, encoding="utf-8")
            self.execute(
                """
                INSERT INTO files(contact_id, original_name, stored_name, category, mime_type, size_bytes, notes, uploaded_by, uploaded_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contact_ids.get(contact_name) if contact_name else None,
                    filename,
                    filename,
                    category,
                    Path(filename).suffix.lower(),
                    path.stat().st_size,
                    "Seed dosyası",
                    user_ids["Admin Yönetici"],
                    (now - timedelta(days=2)).replace(microsecond=0).isoformat(),
                ),
            )

        self.execute("DELETE FROM activities")
        self.execute("DELETE FROM notifications")

        activities = [
            ("Görüşme", "call", "Ayşe Yılmaz ile toplantı tamamlandı", "Demo sunumu başarıyla tamamlandı.", contact_ids["Ayşe Yılmaz"], user_ids["Admin Yönetici"], now - timedelta(minutes=10)),
            ("Satış", "opportunity", "ABC Firma teklifi kabul edildi", "45.000 TL değerindeki teklif başarıyla kapandı.", contact_ids["Ayşe Yılmaz"], user_ids["Admin Yönetici"], now - timedelta(minutes=35)),
            ("Teklif", "opportunity", "Yeni teklif oluşturuldu", "Kadir Tekin için yeni teklif açıldı.", contact_ids["Kadir Tekin"], user_ids["Kaan Erdem"], now - timedelta(hours=1)),
            ("Müşteri", "contact", "Meltem Kaya yeni müşteri olarak eklendi", "MK Holding hesabı CRM'e dahil edildi.", contact_ids["Meltem Kaya"], user_ids["Zeynep Doğan"], now - timedelta(hours=2)),
            ("AI", "contact", "AI risk uyarısı oluşturdu", "Sabri Can için müşteri riski kritik seviyede.", contact_ids["Sabri Can"], user_ids["Admin Yönetici"], now - timedelta(hours=3)),
        ]
        for kind, entity_type, title, description, related_contact_id, related_user_id, created_at in activities:
            self.record_activity(
                kind,
                entity_type,
                related_contact_id,
                title,
                description,
                related_contact_id=related_contact_id,
                related_user_id=related_user_id,
                created_at=created_at.replace(microsecond=0).isoformat(),
            )

        notifications = [
            ("Toplantı yaklaşıyor", "Canan Demir ile bugün planlanan toplantı yaklaşıyor.", "Uyarı", "calls"),
            ("AI risk alarmı", "Sabri Can için müşteri riski kritik seviyede.", "Kritik", "contacts"),
            ("Teklif kabul edildi", "ABC Firma teklifi kabul etti.", "Başarı", "pipeline"),
        ]
        for title, message, severity, action_view in notifications:
            self.create_notification(title, message, severity, action_view)

        self.set_setting("remembered_email", "admin@nexcrm.com")
        self.set_setting("smtp_host", "")
        self.set_setting("smtp_port", "587")
        self.set_setting("smtp_user", "")
        self.set_setting("smtp_sender", "crm@nexcrm.local")
