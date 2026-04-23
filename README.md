# 🚀 NexCRM Pro

Modern, güçlü ve kullanıcı dostu bir **CRM (Customer Relationship Management)** masaüstü uygulaması.
Satış ekiplerinin müşteri ilişkilerini, fırsatlarını ve günlük operasyonlarını tek bir platform üzerinden yönetmesini sağlar.

---

## ⚡ Hızlı Başlangıç

Uygulamayı hızlıca test etmek için:

👉 **`CRM APP.exe` dosyasını çalıştırın**

Kurulum gerektirmez, doğrudan çalışır.

---

## 🧠 Proje Hakkında

NexCRM Pro, müşteri yönetimi, satış pipeline takibi, görev planlama, raporlama ve AI destekli analiz özelliklerini tek bir sistemde birleştiren kapsamlı bir CRM çözümüdür. 

---

## 🎯 Temel Özellikler

### 👥 Müşteri Yönetimi

* Müşteri ekleme, düzenleme ve silme
* Etiket, öncelik ve durum takibi
* Not, dosya ve mail geçmişi

### 📊 Satış & Pipeline

* Fırsat oluşturma ve aşama takibi
* Potansiyel → Görüşme → Teklif → Kazanıldı / Kaybedildi
* Satış performans analizi

### 📅 Planlama & Takip

* Görüşme ve toplantı yönetimi
* Takvim görünümü
* Görev oluşturma ve takip

### 📁 Dosya & Mail Yönetimi

* Dosya yükleme ve arşivleme
* Mail kayıtları ve şablonlar

### 📈 Raporlama

* Dashboard özetleri
* Grafikler ve analizler
* PDF rapor çıktısı

### 🤖 AI Destekli CRM

* Müşteri risk analizi
* Satış önerileri
* Fırsat önceliklendirme
* Otomatik metin ve mail oluşturma

---

## 🖥️ Ana Ekranlar

* Dashboard
* Müşteriler
* Pipeline
* Görüşmeler
* Takvim
* Mail
* Görevler
* Dosyalar
* AI Koç
* Raporlar
* Ekip Yönetimi
* Ayarlar

---

## 🛠️ Kullanılan Teknolojiler

* Python
* PyQt5
* SQLite
* Requests
* OpenRouter API
* QPdfWriter

---

## 📂 Proje Yapısı

```text
CRM_app/
│
├── Kaynak Kodları/
│   └── crm_app/
│       ├── arayuz/
│       ├── veritabani/
│       ├── ai.py
│       ├── yetki.py
│       └── main.py
│
├── scripts/
├── main.py
├── CRMapp_DOKUMANTASYONU.md
├── CRM APP.exe
└── Setup/
```

---

## ⚙️ Kurulum (Kaynak Koddan)

1. Python yüklü olmalı
2. Projeyi indirin
3. Terminal açın:

```bash
python main.py
```

---

## 🧩 Sistem Mimarisi

Uygulama modüler yapıdadır:

* 🎯 **Arayüz Katmanı:** PyQt5 tabanlı UI
* 💾 **Veritabanı Katmanı:** SQLite
* 🔐 **Yetki Katmanı:** Rol bazlı erişim sistemi
* 🤖 **AI Katmanı:** OpenRouter API + lokal analiz

---

## 🧠 AI Özellikleri

* Müşteri AI skoru
* Risk ve fırsat analizi
* Satış önerileri
* CRM verisine göre akıllı yanıtlar
* Mail ve metin üretimi

---

## 🗄️ Veritabanı

Temel tablolar:

* users
* contacts
* opportunities
* tasks
* emails
* files
* notes
* notifications
* settings

Veriler yerel olarak SQLite üzerinde saklanır.

---

## 📌 Not

* Bu repo hem **kaynak kod** hem de **çalıştırılabilir (.exe)** içerir
* EXE hızlı test için eklenmiştir
* Geliştirme için kaynak kod kullanılmalıdır

---

## 👨‍💻 Geliştirici

**Eser Çelik**
Bilgisayar Programcılığı

---

## ⭐ Son Söz

NexCRM Pro, satış ekiplerinin müşteri yönetimini daha düzenli, hızlı ve akıllı hale getirmek için geliştirilmiştir.

Eğer projeyi beğendiysen ⭐ bırakmayı unutma.
