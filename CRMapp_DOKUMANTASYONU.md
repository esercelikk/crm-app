# NexCRM Pro Uygulaması Kısa Dokümantasyon

## 1. Uygulama Tanımı

NexCRM Pro, satış ekiplerinin müşteri ilişkilerini, satış fırsatlarını ve günlük takip süreçlerini tek bir masaüstü uygulaması üzerinden yönetebilmesi için geliştirilmiş bir CRM uygulamasıdır. Uygulama; müşteri yönetimi, pipeline takibi, görüşme planlama, görev yönetimi, mail kayıtları, dosya arşivi, raporlama, ekip yönetimi ve AI destekli satış koçluğu gibi işlevleri tek sistemde toplar.

## 2. Uygulamanın Temel Amacı

Uygulamanın amacı, satış sürecinde oluşan müşteri, fırsat, görüşme, görev ve dosya bilgilerini tek merkezde toplamak ve kullanıcıya düzenli, takip edilebilir ve görsel olarak anlaşılır bir çalışma alanı sunmaktır.

Bu kapsamda kullanıcı:

- müşteri kayıtlarını oluşturabilir ve yönetebilir,
- satış fırsatlarını pipeline aşamalarına göre takip edebilir,
- görüşme, toplantı ve görevlerini planlayabilir,
- müşteri notlarını, mail geçmişini ve dosyalarını saklayabilir,
- satış performansını grafikler ve raporlar üzerinden inceleyebilir,
- AI desteği ile müşteri, risk ve fırsat analizi alabilir.

## 3. Kullanılan Teknolojiler

Uygulamada kullanılan başlıca teknolojiler şunlardır:

- Python
- PyQt5
- SQLite
- Requests
- OpenRouter Chat Completions API
- QPdfWriter
- Python standart dosya ve güvenlik kütüphaneleri

## 4. Temel Özellikler

Uygulamanın mevcut özellikleri aşağıdaki gibidir:

- kullanıcı giriş sistemi
- rol tabanlı kullanıcı ve ekip yönetimi
- açık ve koyu tema desteği
- müşteri ekleme, düzenleme, silme ve arama
- müşteri durum, etiket, öncelik ve sorumlu kullanıcı takibi
- satış fırsatı oluşturma ve pipeline aşaması yönetimi
- görüşme ve toplantı planlama
- takvim görünümü
- görev oluşturma, filtreleme ve tamamlama
- mail kaydı oluşturma ve mail şablonları kullanma
- dosya yükleme, açma, dışa aktarma ve silme
- müşteri notları tutma
- bildirim merkezi
- global arama
- dashboard özetleri ve grafikler
- satış, pipeline, müşteri ve ekip raporları
- PDF rapor çıktısı alma
- AI destekli satış koçu ve CRM analizi
- profil, şifre, SMTP ve AI ayarları yönetimi

## 5. Ana Ekranlar

Uygulama aşağıdaki temel ekranlardan oluşur:

### Giriş

Kullanıcının e-posta ve şifre ile sisteme giriş yaptığı ekrandır. Başarılı girişten sonra ana CRM paneli açılır.

### Dashboard

Kullanıcının genel satış durumunu gördüğü ana paneldir. Bu ekranda aylık satış, pipeline değeri, bekleyen teklifler, bugünkü görüşmeler, riskli müşteriler, son aktiviteler ve AI önerileri yer alır.

### Müşteriler

Tüm müşteri kayıtlarının listelendiği, arandığı ve filtrelendiği ekrandır. Kullanıcı müşterinin firma, iletişim, durum, öncelik, AI skor, risk ve not bilgilerini yönetebilir.

### Pipeline

Satış fırsatlarının aşamalara göre takip edildiği ekrandır. Fırsatlar Potansiyel, Görüşme, Teklif, Kazanıldı ve Kaybedildi gibi aşamalar üzerinden izlenir.

### Görüşmeler

Müşteri görüşmeleri, telefon aramaları ve toplantı kayıtlarının yönetildiği bölümdür. Kullanıcı görüşme tarihi, türü, süresi, sonucu ve notlarını kayıt altına alabilir.

### Takvim

Görevlerin ve planlanan görüşmelerin tarih bazlı görüntülendiği ekrandır. Satış ekibinin günlük ve aylık takiplerini düzenli görmesini sağlar.

### Mail

Müşteriyle yapılan yazılı iletişimin kaydedildiği bölümdür. Mail şablonları sayesinde tekrar eden mesajlar hızlı şekilde hazırlanabilir.

### Görevler

Kullanıcının yapılacak işlerini takip ettiği ekrandır. Görevler öncelik, durum, son tarih ve müşteri ilişkisine göre yönetilebilir.

### Dosyalar

Teklif, belge, rapor ve benzeri dosyaların yüklendiği ve müşteriyle ilişkilendirildiği arşiv ekranıdır.

### AI Koç

CRM verilerine göre satış önerileri, müşteri analizi, risk değerlendirmesi ve metin desteği sunan AI destekli ekrandır.

### Raporlar

Satış performansı, pipeline dağılımı, dönemsel gelir, ekip performansı ve operasyon özetlerinin grafiklerle gösterildiği bölümdür. Raporlar PDF olarak dışa aktarılabilir.

### Ekip

Sistem kullanıcılarının, rollerin ve ekip performansının yönetildiği bölümdür. Roller `Süper Admin`, `Yönetici`, `Satış Müdürü`, `Satış Temsilcisi`, `Destek` ve `Finans` olarak tanımlıdır. Kullanıcı ekleme/düzenleme Süper Admin ve Yönetici ile, kullanıcı silme ise yalnızca Süper Admin ile sınırlandırılır.

### Ayarlar

Profil, şifre, SMTP ve AI API ayarlarının güncellendiği ekrandır.

## 6. AI Destekli Özellikler

Uygulamada AI destekli satış koçu bulunmaktadır. AI katmanı hem uygulama içindeki CRM verilerini analiz eden yerel hesaplamaları hem de OpenRouter API üzerinden çalışan sohbet desteğini içerir.

AI modülü şu işlevleri sağlar:

- müşteri AI skoru hesaplama
- ödeme, potansiyel, sadakat ve kayıp riski analizi
- riskli müşterileri belirleme
- açık fırsatları önceliklendirme
- haftalık satış önerileri üretme
- müşteri özelinde aksiyon tavsiyesi sunma
- CRM verisine göre doğal dilde yanıt verme
- mail, mesaj ve takip metni hazırlamaya yardımcı olma

AI API anahtarı ayarlar ekranından veya ortam değişkenlerinden tanımlanabilir. API anahtarı bulunmadığında uygulama temel yerel analizleri kullanmaya devam eder, ancak API tabanlı sohbet yanıtları çalışmaz.

## 7. Veritabanı Yapısı

Uygulama yerel SQLite veritabanı kullanır. Temel tablolar şunlardır:

- users
- contacts
- opportunities
- calls
- tasks
- emails
- files
- notes
- activities
- notifications
- settings
- mail_templates
- automations

Bu yapı sayesinde kullanıcılar, müşteriler, satış fırsatları, görüşmeler, görevler, mailler, dosyalar, notlar ve bildirimler düzenli ve ilişkisel şekilde saklanır.

## NOT:

Masaüstü kullanım senaryosunda kalıcı veriler uygulama klasörü yerine kullanıcıya ait AppData alanında saklanır. Varsayılan yapı Windows üzerinde veritabanı için `%APPDATA%\NexCRM\data\nexcrm.sqlite` yolunu, yüklenen dosyalar için `%APPDATA%\NexCRM\data\uploads` klasörünü ve rapor çıktıları için `%APPDATA%\NexCRM\data\reports` klasörünü kullanır. Bu sayede uygulama dosyaları taşınsa bile kullanıcı verilerinin daha düzenli ve kalıcı bir alanda tutulması hedeflenir.

## 8. Genel Mimari

Uygulama modüler bir mimari ile geliştirilmiştir. Ana yapı dört katmandan oluşur:

### Başlangıç Katmanı

Kökteki `main.py` dosyası uyumluluk için korunan küçük bir launcher'dır. Asıl başlangıç kodu `Kaynak Kodları/crm_app/main.py` dosyasında yer alır; PyQt5 uygulamasını başlatır, global tema ve font ayarlarını yapar, veritabanı ve AI motorunu oluşturur, giriş ekranından sonra ana pencereyi açar.

### Arayüz Katmanı

`Kaynak Kodları/crm_app/arayuz/` klasöründe yer alır. Ana pencere, giriş ekranı, dialoglar, stiller ve özel widgetlar bu katmanda yönetilir. Dashboard, müşteriler, pipeline, görüşmeler, takvim, mail, görevler, dosyalar, AI, raporlar ve ekip ekranları bu yapı içindedir.

### Veritabanı Katmanı

`Kaynak Kodları/crm_app/veritabani/db.py` dosyasında yer alır. SQLite bağlantısı, tablo oluşturma, varsayılan veri üretimi, kullanıcı doğrulama, CRUD işlemleri, dashboard özetleri ve rapor verileri bu katmanda yönetilir.

### Yetki Katmanı

`Kaynak Kodları/crm_app/yetki.py` dosyasında yer alır. Rol listesi, sayfa erişimleri, işlem bazlı izinler ve rol hedefleri merkezi olarak burada tanımlanır.

### AI Katmanı

`Kaynak Kodları/crm_app/ai.py` dosyasında yer alır. Müşteri skorları, satış önerileri, canlı CRM verisiyle prompt üretimi ve OpenRouter API üzerinden AI yanıtları bu modülde çalışır.

## 9. Çalışma Mantığı

Uygulamanın genel akışı şu şekildedir:

1. Kullanıcı sisteme giriş yapar.
2. Başarılı girişten sonra rolüne uygun ekran ve işlem yetkileri yüklenir.
3. Dashboard ekranı açılır.
4. Kullanıcı yetkisine göre müşteri, fırsat, görev, görüşme, mail veya dosya kayıtlarını yönetir.
5. Yapılan işlemler SQLite veritabanına kaydedilir.
6. Dashboard, takvim, bildirimler ve raporlar güncel verilere göre yenilenir.
7. Gerekirse AI koç CRM verilerini analiz ederek öneri veya yanıt üretir.
8. Yetkili kullanıcılar raporları görüntüleyebilir ve PDF olarak dışa aktarabilir.

## 10. Sonuç

NexCRM Pro, satış ve müşteri ilişkileri yönetimini tek merkezden yürütmek için geliştirilmiş, kullanıcı yönetimi olan, veritabanı destekli, raporlama ve AI bileşenleri içeren bir masaüstü CRM uygulamasıdır. Proje; arayüz, veritabanı, AI ve başlangıç katmanlarının ayrıldığı düzenli bir yapıya sahiptir ve satış ekiplerinin günlük müşteri takibini, fırsat yönetimini ve performans analizini daha kontrollü hale getirmeyi hedefler.
