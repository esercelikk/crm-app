from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from .veritabani.db import DatabaseManager, parse_iso

MONTH_NAMES = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


def _fmt_currency(value: float) -> str:
    return f"₺{value:,.0f}".replace(",", ".")


def _fmt_date(value: str) -> str:
    dt = parse_iso(value)
    if not dt:
        return "-"
    return f"{dt.day:02d} {MONTH_NAMES[dt.month - 1]} {dt.year}"


# ─────────────────────────────────────────────────────────────────────────────
# AIEngine — OpenRouter tabanlı, temiz, akıllı AI motoru
# ─────────────────────────────────────────────────────────────────────────────

class AIEngine:
    """
    OpenRouter-tabanlı AI motoru.

    • API key ve model dinamik olarak veritabanından okunur → ayarlar değişince
      reload_settings() çağrılır, yeni oturum başlar.
    • Sistem prompt'u oturum başında CRM verisiyle BİR KEZ oluşturulur.
    • Kullanıcı mesajı direk gönderilir, her seferinde context sarmaya gerek yok.
    • History son 20 mesajla sınırlıdır (bellek dostu).
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self._history: List[Dict[str, str]] = []
        self._system_prompt: Optional[str] = None

    # ── Ayarlar ──────────────────────────────────────────────────────────────

    def _get_api_key(self) -> str:
        return (
            self.db.get_setting("ai_api_key") or os.getenv("OPENROUTER_API_KEY", "")
        ).strip()

    def _get_model(self) -> str:
        model = (
            self.db.get_setting("ai_model") or os.getenv("OPENROUTER_MODEL", "")
        ).strip()
        return model or "meta-llama/llama-3.1-8b-instruct:free"

    def reload_settings(self) -> None:
        """Ayarlar kaydedildiğinde çağrılır — yeni key/model ile temiz oturum başlar."""
        self.reset_chat_session()

    def reset_chat_session(self) -> None:
        self._history = []
        self._system_prompt = None

    def _quick_local_reply(self, message: str) -> Optional[str]:
        """Basit selam/teşekkür gibi mesajlara API çağırmadan doğal cevap verir."""
        normalized = "".join(
            ch for ch in message.strip().lower()
            if ch.isalnum() or ch.isspace()
        )
        normalized = " ".join(normalized.split())
        greetings = {
            "merhaba", "selam", "slm", "mrb", "hey", "hi", "hello",
            "günaydın", "gunaydin", "iyi günler", "iyi gunler",
            "iyi akşamlar", "iyi aksamlar",
        }
        thanks = {"teşekkürler", "tesekkurler", "sağ ol", "sag ol", "eyvallah", "tşk", "tsk"}
        goodbyes = {"görüşürüz", "gorusuruz", "bay bay", "bye", "çık", "cik"}
        creator_keywords = (
            ("kim yaptı", "kim yapti", "kim geliştirdi", "kim gelistirdi", "kimin yaptığı", "kimin yaptigi")
        )

        if normalized in greetings:
            return (
                "Merhaba, buradayım. CRM verilerini yorumlayabilir, riskli müşterileri çıkarabilir, "
                "fırsat önceliği belirleyebilir veya müşteri için mail metni hazırlayabilirim."
            )
        if (
            any(keyword in normalized for keyword in creator_keywords)
            and ("uygulama" in normalized or "seni" in normalized or "nexcrm" in normalized or "program" in normalized)
        ):
            return "NexCRM uygulamasını ve beni Eser Çelik geliştirdi."
        if normalized in thanks:
            return "Rica ederim. İstersen sıradaki satış aksiyonunu birlikte netleştirebiliriz."
        if normalized in goodbyes:
            return "Görüşürüz. İhtiyaç olduğunda CRM verilerini birlikte hızlıca analiz ederiz."
        return None

    # ── CRM Sistem Prompt'u ───────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """CRM verisini içeren sistem prompt'unu oluşturur (oturumda bir kez çalışır)."""
        crm_lines: List[str] = []
        try:
            summary = self.db.get_dashboard_summary()
            contacts = self.db.list_contacts(sort_by="AI Skor")
            all_opps = self.db.list_opportunities()
            tasks = self.db.list_tasks(include_done=False)

            open_opps = [o for o in all_opps if o["stage"] not in ("Kazanıldı", "Kaybedildi")]
            top_opps = sorted(open_opps, key=lambda o: o.get("value", 0), reverse=True)[:4]
            risk_contacts = sorted(
                [c for c in contacts if c.get("churn_risk", 0) >= 40 or c.get("ai_score", 100) <= 55],
                key=lambda c: (-c.get("churn_risk", 0), c.get("ai_score", 0)),
            )[:4]
            high_contacts = contacts[:4]
            urgent_tasks = [t for t in tasks if t.get("priority") == "Yüksek"][:4]

            today_str = datetime.now().strftime(f"%d {MONTH_NAMES[datetime.now().month - 1]} %Y")
            crm_lines.append(f"[CANLI CRM VERİSİ — {today_str}]")
            crm_lines.append(f"Aylık satış: {_fmt_currency(summary.get('monthly_sales', 0))}")
            crm_lines.append(f"Pipeline değeri: {_fmt_currency(summary.get('pipeline_value', 0))}")
            crm_lines.append(
                f"Bekleyen teklif: {summary.get('pending_offer_count', 0)} adet "
                f"({_fmt_currency(summary.get('pending_offer_value', 0))})"
            )
            crm_lines.append(f"Bugünkü toplantı: {summary.get('today_call_count', 0)}")
            crm_lines.append(f"Risk altındaki müşteri: {summary.get('risk_customer_count', 0)}")
            crm_lines.append(f"Hedef ilerleme: %{summary.get('goal_sales_percent', 0)}")

            if high_contacts:
                crm_lines.append("\nEN İYİ MÜŞTERİLER (AI Skor sıralı):")
                for c in high_contacts:
                    crm_lines.append(
                        f"  • {c['full_name']} / {c.get('company', '')}: "
                        f"Skor {c.get('ai_score', 0)}, "
                        f"Ciro {_fmt_currency(c.get('total_sales', 0))}, "
                        f"Risk %{c.get('churn_risk', 0)}"
                    )

            if risk_contacts:
                crm_lines.append("\nRİSKLİ MÜŞTERİLER:")
                for c in risk_contacts:
                    last = _fmt_date(c.get("last_contact_at", ""))
                    crm_lines.append(
                        f"  • {c['full_name']} / {c.get('company', '')}: "
                        f"Risk %{c.get('churn_risk', 0)}, "
                        f"Skor {c.get('ai_score', 0)}, "
                        f"Son temas: {last}"
                    )

            if top_opps:
                crm_lines.append("\nAÇIK FIRSATLAR (büyükten küçüğe):")
                for o in top_opps:
                    crm_lines.append(
                        f"  • {o.get('contact_company', '?')} — {o.get('title', '?')}: "
                        f"{_fmt_currency(o.get('value', 0))}, "
                        f"Aşama: {o.get('stage', '?')}, "
                        f"Olasılık: %{o.get('probability', 0)}"
                    )

            if urgent_tasks:
                crm_lines.append("\nYÜKSEK ÖNCELİKLİ GÖREVLER:")
                for t in urgent_tasks:
                    due = _fmt_date(t.get("due_at", "")) if t.get("due_at") else "Tarih yok"
                    crm_lines.append(f"  • {t.get('title', '?')} — Son tarih: {due}")

        except Exception:
            crm_lines = []

        base = (
            "KİMLİK VE AMAÇ\n"
            "Sen NexCRM Pro içindeki AI satış asistanısın. Kullanıcının yazdığı sorunun niyetini anlar, "
            "gerekirse canlı CRM verisini kullanır ve doğal Türkçe ile cevap verirsin. Sadece satış raporu veren "
            "katı bir bot değilsin; selamlaşabilir, uygulama hakkında yardımcı olabilir, mail metni yazabilir, "
            "CRM verisini analiz edebilir ve kullanıcının sorduğu konuya doğrudan cevap verebilirsin.\n\n"

            "GELİŞTİRİCİ BİLGİSİ\n"
            "Kullanıcı 'seni kim yaptı', 'uygulamayı kim yaptı', 'NexCRM'i kim geliştirdi' gibi bir soru sorarsa "
            "cevap: 'NexCRM Pro uygulamasını ve beni Eser Çelik geliştirdi.' olmalıdır.\n\n"

            "NİYETİ ANLAMA KURALLARI\n"
            "1. Kullanıcı sadece selam verirse kısa ve sıcak şekilde selam ver; CRM aksiyonu dayatma.\n"
            "2. Kullanıcı teşekkür ederse doğal karşılık ver.\n"
            "3. Kullanıcı uygulama/CRM/satış/müşteri/fırsat/görev/rapor sorarsa aşağıdaki CRM verisini kullan.\n"
            "4. Kullanıcı mail, mesaj, teklif metni veya konuşma taslağı isterse istenen metni üret.\n"
            "5. Kullanıcı genel bir soru sorarsa bildiğin kadarıyla cevapla; CRM verisi gerekmiyorsa CRM verisini zorla kullanma.\n"
            "6. Kullanıcı belirsiz yazarsa en fazla bir netleştirici soru sor veya 2-3 seçenek öner.\n\n"

            "CRM VERİSİ KULLANMA KURALLARI\n"
            "• CRM verisinde isim, şirket, tutar veya tarih varsa somut örnek ver.\n"
            "• Veride olmayan müşteri, fırsat, tutar veya tarih uydurma.\n"
            "• Risk, fırsat ve görev önerilerinde neden-sonuç ilişkisini kısa açıkla.\n"
            "• Veri yetersizse bunu söyle ve hangi verinin eklenmesi gerektiğini belirt.\n\n"

            "ÜSLUP VE FORMAT\n"
            "• Her zaman Türkçe cevap ver.\n"
            "• Doğal, yardımcı ve profesyonel konuş.\n"
            "• Kullanıcının sorusunu merkeze al; gereksiz satış tavsiyesi verme.\n"
            "• Kısa soruya kısa, analiz sorusuna daha detaylı cevap ver.\n"
            "• Markdown başlığı (#), kalın yazı (**), yatay çizgi (---) kullanma.\n"
            "• Liste gerekiyorsa satır başında yalnızca '•' kullan.\n\n"
        )

        if crm_lines:
            base += (
                "ŞU ANKİ CANLI CRM VERİSİ\n"
                + "\n".join(crm_lines)
                + "\n\nKullanıcı CRM ile ilgili bir şey sorarsa bu veriye dayan. "
                "CRM dışı veya basit sohbet sorularında bu veriyi zorla kullanma."
            )
        else:
            base += (
                "Şu an yeterli canlı CRM verisi alınamadı. CRM analizi istenirse veri olmadığını açıkça söyle; "
                "normal sohbet veya genel sorularda yine yardımcı olmaya devam et."
            )

        return base

    # ── Dashboard / Insight yardımcıları (UI tarafından kullanılıyor) ─────────

    def dashboard_brief(self) -> Dict[str, Any]:
        summary = self.db.get_dashboard_summary()
        top_customer = summary.get("top_customer")
        return {
            "title": f"Pipeline içinde {_fmt_currency(summary['pipeline_value'])} tutarında açık fırsat var",
            "subtitle": (
                f"Bu hafta {summary['pending_offer_count']} teklif ve "
                f"{summary['today_call_count']} bugünkü görüşme öncelikli. "
                f"Risk takibinde {summary['risk_customer_count']} müşteri bulunuyor."
            ),
            "top_customer": top_customer["full_name"] if top_customer else "Henüz veri yok",
            "top_customer_note": (
                f"{top_customer['company']} hesabında AI skor {top_customer['ai_score']}"
                if top_customer
                else "Yeni müşteri ekleyerek AI önerilerini zenginleştirebilirsiniz."
            ),
            "risk_count": summary["risk_customer_count"],
            "risk_value": sum(item["total_sales"] for item in summary["risk_customers"]),
            "offer_value": summary["pending_offer_value"],
        }

    def weekly_recommendations(self, limit: int = 3) -> List[str]:
        summary = self.db.get_dashboard_summary()
        opportunities = self.db.list_opportunities()
        contacts = self.db.list_contacts(sort_by="AI Skor")
        tasks = self.db.list_tasks(include_done=False)
        recommendations: List[str] = []

        stage_weights = {"Teklif": 3.2, "Görüşme": 2.4, "Potansiyel": 1.6}
        ranked = sorted(
            [o for o in opportunities if o["stage"] not in ("Kazanıldı", "Kaybedildi")],
            key=lambda o: (o["value"] * stage_weights.get(o["stage"], 1.0)) + (o["contact_ai_score"] * 120),
            reverse=True,
        )
        if ranked:
            top = ranked[0]
            recommendations.append(
                f"{top['contact_name']} / {top['contact_company']} fırsatına öncelik ver. "
                f"{_fmt_currency(top['value'])} tutarında ve {top['stage']} aşamasında ilerliyor."
            )

        risky = sorted(
            [c for c in contacts if c["ai_score"] <= 55 or c["churn_risk"] >= 50],
            key=lambda c: (c["ai_score"], -c["churn_risk"]),
        )
        if risky:
            c = risky[0]
            recommendations.append(
                f"{c['full_name']} hesabını korumaya al. "
                f"Müşteri riski %{c['churn_risk']} ve son temas tarihi eskimeye başlamış."
            )

        urgent = sorted(
            [t for t in tasks if t["priority"] == "Yüksek"],
            key=lambda t: t.get("due_at") or "",
        )
        if urgent:
            recommendations.append(
                f"'{urgent[0]['title']}' görevini bugün tamamla. "
                "Bu aksiyon pipeline akışını doğrudan hızlandırıyor."
            )

        if len(recommendations) < limit and summary["today_call_count"]:
            recommendations.append(
                f"Bugün planlı {summary['today_call_count']} görüşme var. "
                "Görüşme notlarını aynı gün sisteme işleyerek AI skorlarını güncel tut."
            )

        fallbacks = [
            "Müşteri profillerini güncel tutarak AI analizlerinin isabet oranını artırabilirsiniz.",
            "Her satış görüşmesinden sonra kısa bir not bırakmak, bir sonraki adımı netleştirir.",
            "Açık fırsatları haftalık olarak gözden geçirmek dönüşüm oranını yükseltir.",
        ]
        while len(recommendations) < limit and fallbacks:
            tip = fallbacks.pop(0)
            if tip not in recommendations:
                recommendations.append(tip)

        return recommendations[:limit]

    def contact_analysis(self, contact_id: int) -> Dict[str, Any]:
        contact = self.db.get_contact(contact_id)
        if not contact:
            return {
                "score": 0, "payment_score": 0, "potential_score": 0,
                "loyalty_score": 0, "churn_risk": 0,
                "summary": "Müşteri kaydı bulunamadı.",
                "recommendation": "Önce geçerli bir müşteri seçin.",
            }
        calls = self.db.list_calls(contact_id=contact_id)
        opps = self.db.list_opportunities()
        contact_opps = [o for o in opps if o["contact_id"] == contact_id]
        open_value = sum(o["value"] for o in contact_opps if o["stage"] not in ("Kazanıldı", "Kaybedildi"))
        won_value = sum(o["value"] for o in contact_opps if o["stage"] == "Kazanıldı")
        last_contact = parse_iso(contact["last_contact_at"])
        idle_days = (datetime.now() - last_contact).days if last_contact else 999

        if contact["churn_risk"] >= 60:
            rec = "Müşteriyi kaybetmemek için 48 saat içinde yeniden temas kur ve net bir kurtarma teklifi oluştur."
        elif contact["potential_score"] >= 85 and open_value > 0:
            rec = "Bu hesap upsell için çok uygun. Mevcut teklifin üstüne premium veya yıllık paket öner."
        elif idle_days > 14:
            rec = "Uzun süredir temas yok. Kısa bir check-in görüşmesi ve özet mail akışı planla."
        else:
            rec = "İlişki sağlıklı görünüyor. Planlanan görüşmeleri aksatmadan ilerlet ve son notları güncel tut."

        return {
            "score": contact["ai_score"],
            "payment_score": contact["payment_score"],
            "potential_score": contact["potential_score"],
            "loyalty_score": contact["loyalty_score"],
            "churn_risk": contact["churn_risk"],
            "summary": (
                f"{contact['full_name']} hesabında toplam {len(calls)} görüşme, "
                f"{len(contact_opps)} fırsat ve {_fmt_currency(won_value)} kapanmış satış. "
                f"Açık fırsat değeri {_fmt_currency(open_value)}."
            ),
            "recommendation": rec,
        }

    def segment_summary(self) -> Dict[str, int]:
        segments = self.db.get_ai_segments()
        return {
            "high_potential": len(segments["high_potential"]),
            "growth": len(segments["growth"]),
            "passive": len(segments["passive"]),
        }

    # ── Ana Chat Fonksiyonu ───────────────────────────────────────────────────

    def generate_reply(self, message: str) -> str:
        """
        Kullanıcı mesajını OpenRouter'a gönderir ve yanıtı döner.
        • API key yoksa açık hata mesajı döner.
        • History oturum boyunca tutulur (maks 20 mesaj).
        • Model ve key her çağrıda DB'den okunur (ayar değişikliği anında etkili).
        """
        quick_reply = self._quick_local_reply(message)
        if quick_reply:
            return quick_reply

        api_key = self._get_api_key()
        if not api_key:
            return (
                "AI API anahtarı henüz ayarlanmamış.\n"
                "Ayarlar > AI sekmesinden OpenRouter anahtarınızı ekleyin."
            )

        model = self._get_model()

        # CRM verisi her istekte tazelenir; böylece sohbet güncel kayıtlarla cevap verir.
        self._system_prompt = self._build_system_prompt()

        # History'ye kullanıcı mesajını ekle
        self._history.append({"role": "user", "content": message})

        messages = [{"role": "system", "content": self._system_prompt}] + self._history

        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost/",
                    "X-Title": "NexCRM Pro",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
                timeout=30,
            )

            # Hata kodlarına göre açık mesajlar
            if resp.status_code == 401:
                self._history.pop()
                return (
                    "API anahtarı geçersiz veya süresi dolmuş.\n"
                    "Ayarlar > AI bölümünden anahtarınızı kontrol edin."
                )
            if resp.status_code == 429:
                self._history.pop()
                data = resp.json()
                detail = data.get("error", {}).get("message", "Günlük kullanım limiti aşıldı.")
                return f"İstek limiti aşıldı: {detail}"

            if resp.status_code == 400:
                self._history.pop()
                data = resp.json()
                detail = data.get("error", {}).get("message", "")
                return (
                    f"Model '{model}' geçersiz veya desteklenmiyor.\n"
                    f"Detay: {detail}" if detail else
                    f"Model '{model}' geçersiz."
                )

            resp.raise_for_status()

            data = resp.json()
            if "choices" not in data or not data["choices"]:
                raise KeyError(f"Geçersiz JSON yanıtı: {data}")

            reply = data["choices"][0]["message"]["content"].strip()

            # Markdown kalıplarını temizle
            reply = (
                reply
                .replace("**", "")
                .replace("## ", "")
                .replace("# ", "")
                .replace("*", "•")
            )

            # History'ye AI cevabını ekle
            self._history.append({"role": "assistant", "content": reply})

            # History'yi 20 mesajla sınırla (10 gidip-gelen)
            if len(self._history) > 20:
                self._history = self._history[-20:]

            return reply

        except requests.exceptions.Timeout:
            self._history.pop()
            return "Sunucu yanıt vermedi (30 sn zaman aşımı). İnternet bağlantınızı kontrol edip tekrar deneyin."
        except requests.exceptions.ConnectionError:
            self._history.pop()
            return "Bağlantı kurulamadı. İnternet erişiminizi kontrol edin."
        except (KeyError, IndexError):
            self._history.pop()
            return "AI yanıtı beklenmedik formatta geldi. Lütfen tekrar deneyin."
        except Exception as exc:
            self._history.pop()
            return f"Beklenmeyen bir hata oluştu: {exc}"
