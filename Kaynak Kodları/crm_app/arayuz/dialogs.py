from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from PyQt5.QtCore import QDate, QDateTime, QTime, Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..veritabani.db import (
    CALL_OUTCOME_OPTIONS,
    CALL_TYPE_OPTIONS,
    PRIORITY_OPTIONS,
    ROLE_OPTIONS,
    STATUS_OPTIONS,
    TAG_OPTIONS,
    parse_iso,
)
from .widgets import StarRatingInput

# Bu dosya CRM'deki kayıt ekleme/düzenleme pencerelerini içerir.
# Her dialog, form alanlarını doğrulayıp veritabanı katmanına uygun payload döndürür.


# Veritabanından gelen ISO tarih metnini Qt tarih-saat bileşenine çevirir.
def to_qdatetime(value: Optional[str]) -> QDateTime:
    dt = parse_iso(value) or datetime.now()
    return QDateTime(QDate(dt.year, dt.month, dt.day), QTime(dt.hour, dt.minute))


# Qt tarih-saat alanındaki değeri veritabanına yazılacak ISO metnine çevirir.
def to_iso(value: QDateTimeEdit) -> str:
    return value.dateTime().toPyDateTime().replace(second=0, microsecond=0).isoformat()


# Form alanlarına ortak DialogInput stil kimliğini verir.
def mark_dialog_input(widget: QWidget) -> QWidget:
    widget.setObjectName("DialogInput")
    return widget


# Liste verilerini QComboBox içine görünen metin + gerçek ID olarak doldurur.
def fill_combo(combo: QComboBox, rows: Iterable[Dict[str, Any]], label_key: str = "full_name", value_key: str = "id", blank_label: str = "Seçiniz", include_blank: bool = True) -> None:
    combo.clear()
    if include_blank:
        combo.addItem(blank_label, None)
    for row in rows:
        combo.addItem(str(row[label_key]), row[value_key])


# ComboBox içinde kayıt ID'sine göre ilgili satırı seçer.
def select_combo_value(combo: QComboBox, value: Any) -> None:
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            combo.setCurrentIndex(index)
            return


# Tüm kayıt formlarının ortak başlık, scroll alanı ve kaydet/iptal iskeleti.
class BaseDialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(520, 540)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(28, 24, 28, 20)
        self.root.setSpacing(14)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionTitle")
        self.subtitle_label = QLabel("Bilgileri doldurup kaydedin.")
        self.subtitle_label.setObjectName("SectionSubtitle")
        self.root.addWidget(self.title_label)
        self.root.addWidget(self.subtitle_label)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(14)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        self.root.addWidget(self.scroll, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        cancel_button = self.button_box.button(QDialogButtonBox.Cancel)
        ok_button.setText("Kaydet")
        cancel_button.setText("İptal")
        ok_button.setObjectName("PrimaryButton")
        cancel_button.setObjectName("GhostButton")
        self.root.addWidget(self.button_box)
        self.button_box.accepted.connect(self._try_accept)
        self.button_box.rejected.connect(self.reject)

    def warn(self, message: str) -> None:
        QMessageBox.warning(self, "Eksik bilgi", message)

    # Kaydetmeden önce ilgili dialog'un get_data doğrulamasını çalıştırır.
    def _try_accept(self) -> None:
        getter = getattr(self, "get_data", None)
        if callable(getter) and getter() is None:
            return
        super().accept()


# Müşteri ekleme/düzenleme formu.
class ContactDialog(BaseDialog):
    """Sadeleştirilmiş müşteri formu — skor alanları kaldırıldı, yıldız sistemi eklendi."""

    def __init__(self, users: List[Dict[str, Any]], contact: Optional[Dict[str, Any]] = None, parent: QWidget | None = None) -> None:
        super().__init__("Müşteri Kaydı", parent)
        self.users = users
        self.contact = contact

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)

        self.full_name = mark_dialog_input(QLineEdit())
        self.full_name.setPlaceholderText("Müşteri adı soyadı")
        self.company = mark_dialog_input(QLineEdit())
        self.company.setPlaceholderText("Firma adı")
        self.title = mark_dialog_input(QLineEdit())
        self.title.setPlaceholderText("Ünvan (opsiyonel)")
        self.phone = mark_dialog_input(QLineEdit())
        self.phone.setPlaceholderText("+90 5XX XXX XX XX")
        self.email = mark_dialog_input(QLineEdit())
        self.email.setPlaceholderText("email@firma.com")
        self.status = mark_dialog_input(QComboBox())
        self.status.addItems(STATUS_OPTIONS)
        self.priority = mark_dialog_input(QComboBox())
        self.priority.addItems(PRIORITY_OPTIONS)
        self.tag = mark_dialog_input(QComboBox())
        self.tag.addItems(TAG_OPTIONS)
        self.assigned = mark_dialog_input(QComboBox())
        fill_combo(self.assigned, users)
        self.star_rating = StarRatingInput(initial=3, size=22)
        self.notes = mark_dialog_input(QTextEdit())
        self.notes.setMinimumHeight(52)
        self.notes.setPlaceholderText("Müşteri hakkında notlar...")

        rows = [
            ("Ad Soyad", self.full_name),
            ("Firma", self.company),
            ("Ünvan", self.title),
            ("Telefon", self.phone),
            ("E-posta", self.email),
            ("Durum", self.status),
            ("Öncelik", self.priority),
            ("Etiket", self.tag),
            ("Sorumlu", self.assigned),
            ("Değerlendirme", self.star_rating),
            ("Notlar", self.notes),
        ]
        for label, widget in rows:
            form.addRow(label, widget)
        self.body_layout.addLayout(form)

        if contact:
            self.full_name.setText(contact["full_name"])
            self.company.setText(contact["company"])
            self.title.setText(contact.get("title") or "")
            self.phone.setText(contact.get("phone") or "")
            self.email.setText(contact.get("email") or "")
            self.status.setCurrentText(contact["status"])
            self.priority.setCurrentText(contact["priority"])
            self.tag.setCurrentText(contact.get("tag") or "Yeni")
            select_combo_value(self.assigned, contact.get("assigned_user_id"))
            from .widgets import StarRatingWidget
            stars = StarRatingWidget.score_to_stars(int(contact.get("ai_score") or 55))
            self.star_rating._set_value(stars)
            self.notes.setPlainText(contact.get("notes") or "")

    def get_data(self) -> Optional[Dict[str, Any]]:
        # Zorunlu müşteri alanları kontrol edilir, yıldız puanı CRM skorlarına çevrilir.
        if not self.full_name.text().strip():
            self.warn("Müşteri adı zorunlu.")
            return None
        if not self.company.text().strip():
            self.warn("Firma alanı zorunlu.")
            return None
        score = StarRatingInput.stars_to_score(self.star_rating.value())
        return {
            "full_name": self.full_name.text(),
            "company": self.company.text(),
            "title": self.title.text(),
            "phone": self.phone.text(),
            "email": self.email.text(),
            "status": self.status.currentText(),
            "priority": self.priority.currentText(),
            "tag": self.tag.currentText(),
            "assigned_user_id": self.assigned.currentData(),
            "payment_score": score,
            "potential_score": score,
            "loyalty_score": score,
            "churn_risk": max(8, 80 - score),
            "notes": self.notes.toPlainText(),
        }


# Satış fırsatı ekleme/düzenleme formu.
class OpportunityDialog(BaseDialog):
    def __init__(self, contacts: List[Dict[str, Any]], users: List[Dict[str, Any]], opportunity: Optional[Dict[str, Any]] = None, parent: QWidget | None = None) -> None:
        super().__init__("Fırsat Kaydı", parent)
        self.contacts = contacts
        self.users = users
        self.opportunity = opportunity

        form = QFormLayout()
        form.setSpacing(10)
        self.contact = mark_dialog_input(QComboBox())
        fill_combo(self.contact, [{"id": c["id"], "full_name": f"{c['full_name']} - {c['company']}"} for c in contacts], include_blank=False)
        self.title_input = mark_dialog_input(QLineEdit())
        self.title_input.setPlaceholderText("Fırsat başlığı")
        self.stage = mark_dialog_input(QComboBox())
        self.stage.addItems(["Potansiyel", "Görüşme", "Teklif", "Kazanıldı", "Kaybedildi"])
        self.value = mark_dialog_input(QSpinBox())
        self.value.setRange(0, 100000000)
        self.value.setSingleStep(1000)
        self.value.setPrefix("₺ ")
        self.owner = mark_dialog_input(QComboBox())
        fill_combo(self.owner, users)
        self.expected_close = mark_dialog_input(QDateTimeEdit())
        self.expected_close.setCalendarPopup(True)
        self.expected_close.setDateTime(to_qdatetime(opportunity["expected_close"] if opportunity else None))
        self.notes = mark_dialog_input(QTextEdit())
        self.notes.setMinimumHeight(90)
        self.notes.setPlaceholderText("Fırsat ile ilgili notlar...")

        for label, widget in [
            ("Müşteri", self.contact),
            ("Başlık", self.title_input),
            ("Aşama", self.stage),
            ("Tutar", self.value),
            ("Sorumlu", self.owner),
            ("Beklenen kapanış", self.expected_close),
            ("Notlar", self.notes),
        ]:
            form.addRow(label, widget)
        self.body_layout.addLayout(form)

        if opportunity:
            select_combo_value(self.contact, opportunity["contact_id"])
            self.title_input.setText(opportunity["title"])
            self.stage.setCurrentText(opportunity["stage"])
            self.value.setValue(int(opportunity["value"]))
            select_combo_value(self.owner, opportunity.get("owner_user_id"))
            self.notes.setPlainText(opportunity.get("notes") or "")

    def get_data(self) -> Optional[Dict[str, Any]]:
        # Fırsat stage bilgisine göre kapanış olasılığı otomatik atanır.
        if not self.title_input.text().strip():
            self.warn("Fırsat başlığı zorunlu.")
            return None
        if self.contact.currentData() is None:
            self.warn("Bir müşteri seçmelisiniz.")
            return None
        stage_probs = {"Potansiyel": 20, "Görüşme": 50, "Teklif": 75, "Kazanıldı": 100, "Kaybedildi": 0}
        return {
            "contact_id": self.contact.currentData(),
            "title": self.title_input.text(),
            "stage": self.stage.currentText(),
            "value": self.value.value(),
            "probability": stage_probs.get(self.stage.currentText(), 50),
            "owner_user_id": self.owner.currentData(),
            "expected_close": to_iso(self.expected_close),
            "notes": self.notes.toPlainText(),
        }


# Görüşme veya toplantı planlama/düzenleme formu.
class CallDialog(BaseDialog):
    def __init__(self, contacts: List[Dict[str, Any]], users: List[Dict[str, Any]], call: Optional[Dict[str, Any]] = None, parent: QWidget | None = None) -> None:
        super().__init__("Görüşme / Toplantı", parent)
        self.contacts = contacts
        self.users = users
        form = QFormLayout()
        form.setSpacing(10)

        self.contact = mark_dialog_input(QComboBox())
        fill_combo(self.contact, [{"id": c["id"], "full_name": f"{c['full_name']} - {c['company']}"} for c in contacts], include_blank=False)
        self.call_type = mark_dialog_input(QComboBox())
        self.call_type.addItems(CALL_TYPE_OPTIONS)
        self.when = mark_dialog_input(QDateTimeEdit())
        self.when.setCalendarPopup(True)
        self.when.setDateTime(to_qdatetime(call["scheduled_at"] if call else None))
        self.duration = mark_dialog_input(QSpinBox())
        self.duration.setRange(5, 480)
        self.duration.setSuffix(" dk")
        self.duration.setValue(int(call["duration_minutes"]) if call else 30)
        self.outcome = mark_dialog_input(QComboBox())
        self.outcome.addItems(CALL_OUTCOME_OPTIONS)
        self.owner = mark_dialog_input(QComboBox())
        fill_combo(self.owner, users)
        self.notes = mark_dialog_input(QTextEdit())
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Görüşme notları...")

        for label, widget in [
            ("Müşteri", self.contact),
            ("Tür", self.call_type),
            ("Tarih ve saat", self.when),
            ("Süre", self.duration),
            ("Sonuç", self.outcome),
            ("Sorumlu", self.owner),
            ("Notlar", self.notes),
        ]:
            form.addRow(label, widget)
        self.body_layout.addLayout(form)

        if call:
            select_combo_value(self.contact, call["contact_id"])
            self.call_type.setCurrentText(call["call_type"])
            self.outcome.setCurrentText(call["outcome"])
            select_combo_value(self.owner, call.get("owner_user_id"))
            self.notes.setPlainText(call.get("notes") or "")

    def get_data(self) -> Optional[Dict[str, Any]]:
        # Görüşme mutlaka bir müşteriye bağlı kaydedilir.
        if self.contact.currentData() is None:
            self.warn("Görüşme için müşteri seçmelisiniz.")
            return None
        return {
            "contact_id": self.contact.currentData(),
            "call_type": self.call_type.currentText(),
            "scheduled_at": to_iso(self.when),
            "duration_minutes": self.duration.value(),
            "outcome": self.outcome.currentText(),
            "reminder_at": None,
            "owner_user_id": self.owner.currentData(),
            "notes": self.notes.toPlainText(),
        }


# Görev ekleme/düzenleme formu.
class TaskDialog(BaseDialog):
    def __init__(self, contacts: List[Dict[str, Any]], users: List[Dict[str, Any]], task: Optional[Dict[str, Any]] = None, parent: QWidget | None = None) -> None:
        super().__init__("Görev", parent)
        form = QFormLayout()
        form.setSpacing(10)

        self.title_input = mark_dialog_input(QLineEdit())
        self.title_input.setPlaceholderText("Görev başlığı")
        self.description = mark_dialog_input(QTextEdit())
        self.description.setMinimumHeight(80)
        self.description.setPlaceholderText("Açıklama...")
        self.priority = mark_dialog_input(QComboBox())
        self.priority.addItems(PRIORITY_OPTIONS)
        self.due_at = mark_dialog_input(QDateTimeEdit())
        self.due_at.setCalendarPopup(True)
        self.due_at.setDateTime(to_qdatetime(task["due_at"] if task else None))
        self.assigned = mark_dialog_input(QComboBox())
        fill_combo(self.assigned, users)
        self.contact = mark_dialog_input(QComboBox())
        fill_combo(self.contact, [{"id": c["id"], "full_name": f"{c['full_name']} - {c['company']}"} for c in contacts], include_blank=True, blank_label="Bağlantı yok")
        self.done = QCheckBox("Görev tamamlandı")

        for label, widget in [
            ("Başlık", self.title_input),
            ("Açıklama", self.description),
            ("Öncelik", self.priority),
            ("Bitiş tarihi", self.due_at),
            ("Atanan kişi", self.assigned),
            ("Bağlı müşteri", self.contact),
        ]:
            form.addRow(label, widget)
        form.addRow("", self.done)
        self.body_layout.addLayout(form)

        if task:
            self.title_input.setText(task["title"])
            self.description.setPlainText(task.get("description") or "")
            self.priority.setCurrentText(task["priority"])
            select_combo_value(self.assigned, task.get("assigned_user_id"))
            select_combo_value(self.contact, task.get("contact_id"))
            self.done.setChecked(bool(task.get("is_done")))

    def get_data(self) -> Optional[Dict[str, Any]]:
        # Görevin temel bilgileri UI'dan alınır ve veritabanı payload'una çevrilir.
        if not self.title_input.text().strip():
            self.warn("Görev başlığı boş olamaz.")
            return None
        return {
            "title": self.title_input.text(),
            "description": self.description.toPlainText(),
            "priority": self.priority.currentText(),
            "due_at": to_iso(self.due_at),
            "assigned_user_id": self.assigned.currentData(),
            "contact_id": self.contact.currentData(),
            "is_done": self.done.isChecked(),
            "status": "Tamamlandı" if self.done.isChecked() else "Bekliyor",
            "owner_user_id": self.assigned.currentData(),
        }


# Mail kaydı oluşturma formu; müşteri ve şablon seçimini destekler.
class EmailDialog(BaseDialog):
    def __init__(
        self,
        contacts: List[Dict[str, Any]],
        templates: List[Dict[str, Any]],
        email: Optional[Dict[str, Any]] = None,
        preselected_contact_id: Optional[int] = None,
        template_name: Optional[str] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Mail Oluştur", parent)
        self.contacts = contacts
        self.templates = templates
        self.email = email

        form = QFormLayout()
        form.setSpacing(10)
        self.contact = mark_dialog_input(QComboBox())
        fill_combo(self.contact, [{"id": c["id"], "full_name": f"{c['full_name']} - {c['email']}"} for c in contacts], include_blank=True, blank_label="Harici alıcı")
        self.recipient = mark_dialog_input(QLineEdit())
        self.recipient.setPlaceholderText("alici@firma.com")
        self.subject = mark_dialog_input(QLineEdit())
        self.subject.setPlaceholderText("Mail konusu")
        self.template = mark_dialog_input(QComboBox())
        self.template.addItem("Şablon yok", None)
        for item in templates:
            self.template.addItem(item["name"], item)
        self.body_text = mark_dialog_input(QPlainTextEdit())
        self.body_text.setMinimumHeight(160)
        self.body_text.setPlaceholderText("Mail içeriğini yazın...")

        for label, widget in [
            ("Müşteri", self.contact),
            ("Alıcı", self.recipient),
            ("Konu", self.subject),
            ("Şablon", self.template),
            ("İçerik", self.body_text),
        ]:
            form.addRow(label, widget)
        self.body_layout.addLayout(form)

        self.contact.currentIndexChanged.connect(self._sync_recipient)
        self.template.currentIndexChanged.connect(self._apply_template)

        if preselected_contact_id:
            select_combo_value(self.contact, preselected_contact_id)
            self._sync_recipient()
        if template_name:
            for index in range(self.template.count()):
                template = self.template.itemData(index)
                if template and template["name"] == template_name:
                    self.template.setCurrentIndex(index)
                    break
        if email:
            select_combo_value(self.contact, email.get("contact_id"))
            self.recipient.setText(email["recipient"])
            self.subject.setText(email["subject"])
            self.body_text.setPlainText(email["body"])

    def _sync_recipient(self) -> None:
        # Müşteri seçilince kayıtlı e-posta alıcı alanına otomatik yazılır.
        selected = self.contact.currentData()
        for contact in self.contacts:
            if contact["id"] == selected:
                self.recipient.setText(contact.get("email") or "")
                return

    def _apply_template(self) -> None:
        # Şablondaki {{ad}} alanı seçili müşteri adıyla doldurulur.
        template = self.template.currentData()
        if not template:
            return
        selected_name = ""
        selected = self.contact.currentData()
        for contact in self.contacts:
            if contact["id"] == selected:
                selected_name = contact["full_name"]
                break
        subject = template["subject"]
        body = template["body"].replace("{{ad}}", selected_name or "Müşteri")
        if not self.subject.text().strip():
            self.subject.setText(subject)
        if not self.body_text.toPlainText().strip():
            self.body_text.setPlainText(body)

    def get_data(self) -> Optional[Dict[str, Any]]:
        # Mail CRM içinde giden kayıt olarak saklanacak payload'a dönüştürülür.
        if not self.recipient.text().strip():
            self.warn("Alıcı e-posta zorunlu.")
            return None
        if not self.subject.text().strip():
            self.warn("Mail konusu boş olamaz.")
            return None
        if not self.body_text.toPlainText().strip():
            self.warn("Mail içeriği boş olamaz.")
            return None
        template = self.template.currentData()
        return {
            "contact_id": self.contact.currentData(),
            "recipient": self.recipient.text(),
            "subject": self.subject.text(),
            "body": self.body_text.toPlainText(),
            "template_name": template["name"] if template else None,
            "status": "Gönderildi",
            "direction": "Giden",
            "is_unread": 0,
        }


# Ekip kullanıcısı ekleme/düzenleme formu.
class UserDialog(BaseDialog):
    def __init__(self, user: Optional[Dict[str, Any]] = None, parent: QWidget | None = None) -> None:
        super().__init__("Kullanıcı", parent)
        form = QFormLayout()
        form.setSpacing(10)

        self.full_name = mark_dialog_input(QLineEdit())
        self.email = mark_dialog_input(QLineEdit())
        self.phone = mark_dialog_input(QLineEdit())
        self.role = mark_dialog_input(QComboBox())
        self.role.addItems(ROLE_OPTIONS)
        self.password = mark_dialog_input(QLineEdit())
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Boş bırakırsanız mevcut şifre korunur")
        self.is_active = QCheckBox("Kullanıcı aktif")
        self.is_active.setChecked(True)

        for label, widget in [
            ("Ad Soyad", self.full_name),
            ("E-posta", self.email),
            ("Telefon", self.phone),
            ("Rol", self.role),
            ("Şifre", self.password),
        ]:
            form.addRow(label, widget)
        form.addRow("", self.is_active)
        self.body_layout.addLayout(form)

        if user:
            self.full_name.setText(user["full_name"])
            self.email.setText(user["email"])
            self.phone.setText(user.get("phone") or "")
            self.role.setCurrentText(user["role"])
            self.is_active.setChecked(bool(user["is_active"]))

    def get_data(self) -> Optional[Dict[str, Any]]:
        # Kullanıcı kimliği için ad ve e-posta zorunlu tutulur.
        if not self.full_name.text().strip():
            self.warn("Kullanıcı adı zorunlu.")
            return None
        if not self.email.text().strip():
            self.warn("E-posta zorunlu.")
            return None
        return {
            "full_name": self.full_name.text(),
            "email": self.email.text(),
            "phone": self.phone.text(),
            "role": self.role.currentText(),
            "password": self.password.text(),
            "is_active": self.is_active.isChecked(),
        }


# Müşteri detayında kullanılan kısa not ekleme formu.
class NoteDialog(BaseDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Müşteri Notu", parent)
        form = QFormLayout()
        self.title_input = mark_dialog_input(QLineEdit())
        self.title_input.setPlaceholderText("Not başlığı")
        self.content = mark_dialog_input(QTextEdit())
        self.content.setMinimumHeight(140)
        self.content.setPlaceholderText("Not içeriğini yazın...")
        form.addRow("Başlık", self.title_input)
        form.addRow("İçerik", self.content)
        self.body_layout.addLayout(form)

    def get_data(self) -> Optional[Dict[str, Any]]:
        # Boş başlık veya içerik ile not kaydı oluşturulmasını engeller.
        if not self.title_input.text().strip():
            self.warn("Not başlığı zorunlu.")
            return None
        if not self.content.toPlainText().strip():
            self.warn("Not içeriği boş olamaz.")
            return None
        return {"title": self.title_input.text(), "content": self.content.toPlainText()}


# Profil, güvenlik, SMTP ve AI ayarlarının tek pencerede yönetildiği dialog.
class SettingsDialog(QDialog):
    def __init__(
        self,
        current_user: Dict[str, Any],
        settings: Dict[str, str],
        parent: QWidget | None = None,
        allow_system_settings: bool = True,
    ) -> None:
        super().__init__(parent)
        self.allow_system_settings = allow_system_settings
        self.setWindowTitle("Ayarlar")
        self.resize(600, 480)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(14)

        title = QLabel("Uygulama Ayarları")
        title.setObjectName("SectionTitle")
        subtitle_text = "Profil, güvenlik ve mail ayarlarını yönetin." if allow_system_settings else "Profil ve güvenlik bilgilerinizi yönetin."
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("SectionSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.profile_tab = QWidget()
        profile_form = QFormLayout(self.profile_tab)
        profile_form.setSpacing(10)
        self.profile_name = mark_dialog_input(QLineEdit(current_user["full_name"]))
        self.profile_email = mark_dialog_input(QLineEdit(current_user["email"]))
        self.profile_phone = mark_dialog_input(QLineEdit(current_user.get("phone") or ""))
        profile_form.addRow("Ad Soyad", self.profile_name)
        profile_form.addRow("E-posta", self.profile_email)
        profile_form.addRow("Telefon", self.profile_phone)
        self.tabs.addTab(self.profile_tab, "Profil")

        self.security_tab = QWidget()
        security_form = QFormLayout(self.security_tab)
        security_form.setSpacing(10)
        self.current_password = mark_dialog_input(QLineEdit())
        self.current_password.setEchoMode(QLineEdit.Password)
        self.new_password = mark_dialog_input(QLineEdit())
        self.new_password.setEchoMode(QLineEdit.Password)
        self.confirm_password = mark_dialog_input(QLineEdit())
        self.confirm_password.setEchoMode(QLineEdit.Password)
        security_form.addRow("Mevcut şifre", self.current_password)
        security_form.addRow("Yeni şifre", self.new_password)
        security_form.addRow("Tekrar", self.confirm_password)
        self.tabs.addTab(self.security_tab, "Güvenlik")

        self.smtp_host = None
        self.smtp_port = None
        self.smtp_user = None
        self.smtp_sender = None
        self.ai_api_key = None
        self.ai_model = None

        if allow_system_settings:
            self.smtp_tab = QWidget()
            smtp_form = QGridLayout(self.smtp_tab)
            smtp_form.setSpacing(10)
            self.smtp_host = mark_dialog_input(QLineEdit(settings.get("smtp_host", "")))
            self.smtp_port = mark_dialog_input(QLineEdit(settings.get("smtp_port", "587")))
            self.smtp_user = mark_dialog_input(QLineEdit(settings.get("smtp_user", "")))
            self.smtp_sender = mark_dialog_input(QLineEdit(settings.get("smtp_sender", "")))
            smtp_form.addWidget(QLabel("SMTP Host"), 0, 0)
            smtp_form.addWidget(self.smtp_host, 1, 0)
            smtp_form.addWidget(QLabel("Port"), 0, 1)
            smtp_form.addWidget(self.smtp_port, 1, 1)
            smtp_form.addWidget(QLabel("Kullanıcı"), 2, 0)
            smtp_form.addWidget(self.smtp_user, 3, 0)
            smtp_form.addWidget(QLabel("Gönderici"), 2, 1)
            smtp_form.addWidget(self.smtp_sender, 3, 1)
            self.tabs.addTab(self.smtp_tab, "SMTP")

            self.ai_tab = QWidget()
            ai_form = QFormLayout(self.ai_tab)
            ai_form.setSpacing(10)
            self.ai_api_key = mark_dialog_input(QLineEdit(settings.get("ai_api_key", "")))
            self.ai_api_key.setEchoMode(QLineEdit.Password)
            self.ai_api_key.setPlaceholderText("sk-or-... (OpenRouter API key)")
            self.ai_model = mark_dialog_input(QLineEdit(settings.get("ai_model", "openrouter/free")))
            self.ai_model.setPlaceholderText("openrouter/free")
            ai_hint = QLabel("Not: Bu anahtar AI sohbet yanıtları için kullanılır.")
            ai_hint.setObjectName("SectionSubtitle")
            ai_form.addRow("OpenRouter API Key", self.ai_api_key)
            ai_form.addRow("Model", self.ai_model)
            ai_form.addRow("", ai_hint)
            self.tabs.addTab(self.ai_tab, "AI")

        button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        save_button = button_box.button(QDialogButtonBox.Ok)
        close_button = button_box.button(QDialogButtonBox.Cancel)
        save_button.setText("Kaydet")
        close_button.setText("Kapat")
        save_button.setObjectName("PrimaryButton")
        close_button.setObjectName("GhostButton")
        root.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def get_profile_payload(self) -> Dict[str, str]:
        # Profil sekmesindeki temel kullanıcı bilgilerini döndürür.
        return {
            "full_name": self.profile_name.text(),
            "email": self.profile_email.text(),
            "phone": self.profile_phone.text(),
        }

    def get_password_payload(self) -> Dict[str, str]:
        # Güvenlik sekmesindeki şifre değiştirme alanlarını döndürür.
        return {
            "current_password": self.current_password.text(),
            "new_password": self.new_password.text(),
            "confirm_password": self.confirm_password.text(),
        }

    def get_smtp_payload(self) -> Dict[str, str]:
        # SMTP sekmesindeki mail sunucusu ayarlarını döndürür.
        if not self.allow_system_settings:
            return {}
        return {
            "smtp_host": self.smtp_host.text(),
            "smtp_port": self.smtp_port.text(),
            "smtp_user": self.smtp_user.text(),
            "smtp_sender": self.smtp_sender.text(),
        }

    def get_ai_payload(self) -> Dict[str, str]:
        # AI sekmesindeki API key ve model ayarlarını döndürür.
        if not self.allow_system_settings:
            return {}
        return {
            "ai_api_key": self.ai_api_key.text().strip(),
            "ai_model": self.ai_model.text().strip() or "openrouter/free",
        }


# Sadece AI ayarlarını hızlıca değiştirmek için kullanılan küçük dialog.
class AISettingsDialog(QDialog):
    def __init__(self, settings: Dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Ayarları")
        self.resize(500, 300)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(14)

        title = QLabel("AI Konfigürasyonu")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("API anahtarı ve model ayarlarını yönetin.")
        subtitle.setObjectName("SectionSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        ai_form = QFormLayout()
        ai_form.setSpacing(10)
        self.ai_api_key = mark_dialog_input(QLineEdit(settings.get("ai_api_key", "")))
        self.ai_api_key.setEchoMode(QLineEdit.Password)
        self.ai_api_key.setPlaceholderText("sk-or-... (OpenRouter API key)")
        self.ai_model = mark_dialog_input(QLineEdit(settings.get("ai_model", "openrouter/free")))
        self.ai_model.setPlaceholderText("openrouter/free")
        ai_hint = QLabel("Not: Bu anahtar AI sohbet yanıtları için kullanılır.")
        ai_hint.setObjectName("SectionSubtitle")
        ai_form.addRow("OpenRouter API Key", self.ai_api_key)
        ai_form.addRow("Model", self.ai_model)
        ai_form.addRow("", ai_hint)
        root.addLayout(ai_form)
        root.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        save_button = button_box.button(QDialogButtonBox.Ok)
        close_button = button_box.button(QDialogButtonBox.Cancel)
        save_button.setText("Kaydet")
        close_button.setText("Kapat")
        save_button.setObjectName("PrimaryButton")
        close_button.setObjectName("GhostButton")
        root.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def get_ai_payload(self) -> Dict[str, str]:
        # Boş model bırakılırsa uygulamanın varsayılan model adı kullanılır.
        return {
            "ai_api_key": self.ai_api_key.text().strip(),
            "ai_model": self.ai_model.text().strip() or "openrouter/free",
        }
