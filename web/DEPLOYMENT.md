# Day Trader TR: özel kullanım ve 0 TL başlangıç

Durum: giriş koruması ve bulut çalıştırma dosyaları hazır. Henüz yayın yok.
Gerçek bulut veritabanı ve iPhone kabul testi tamamlanmadan yayın onayı istenmemeli.

## Yerel kullanım

Python 3.9+ ile `python3 -m web.auth` çalıştırın. Parola gizli girilir; ekranda
sadece rastgele tuzlu PBKDF2-SHA256 (600.000 tur) özeti gösterilir.
En az 14 karakterli benzersiz bir parola seçin. Parolayı sohbete yazmayın.
Özeti `PAPER_PASSWORD_HASH` ortam değişkenine koyun; GitHub'a yüklemeyin.
`.env.example` yalnızca boş örnektir; uygulama `.env` dosyalarını otomatik okumaz.
Yerelde `PAPER_LOCAL_HTTP=1` ile `python3 -m web.server` çalıştırın.
Bu HTTP istisnasını bulutta kullanmayın. Varsayılan adres yalnızca localhost'tur.

Oturum 12 saat sürer. HttpOnly/SameSite=Strict ve bulutta Secure çerez kullanılır.
Çıkış oturumu iptal eder. Beş yanlış giriş tüm uygulama için beş dakikalık bekleme
oluşturur. Bu tek kullanıcı için basit bir savunmadır; saldırgan geçici erişim
engeli oluşturabilir. Sunucu yeniden başladığında oturumlar ve bekleme sayacı
sıfırlanır. Tek Gunicorn worker zorunludur; oturumlar süreç belleğindedir.
Parola özeti değiştirilip servis yeniden başlatılınca tüm oturumlar kapanır.

## Ücretsiz bulut hedefi

Render Free web servisi + Supabase Free PostgreSQL önerilen başlangıçtır.
Bu bir yayın talimatı/onayı değildir. Hesap veya hizmet oluşturulmadı.
MacBook kapalıyken uygulama bulut sunucusunda çalışır; iPhone HTTPS adresini açar.
Render Free 15 dakika hareketsizlikten sonra uyur; ilk açılış bekletebilir.
Ücretsiz katmanlar kesintisiz çalışma garantisi vermez. Supabase düşük kullanımda
bir haftadan sonra duraklatabilir. Ücretsiz sınır aşımında ücretli plana otomatik
geçiş yapılmamalı; limitte durmak kabul edilir. Ücretli disk ve Render'ın süreli
ücretsiz PostgreSQL hizmeti seçilmemeli.

Kaynaklar (12 Kasım 2026 tarihinde kontrol edildi):
- https://render.com/docs/free
- https://render.com/docs/disks
- https://supabase.com/pricing
- https://supabase.com/docs/guides/platform/free-project-pausing

## Veri kalıcılığı

Yerelde kayıtlar `.web-data/paper.sqlite3` dosyasındadır. GitHub'da değildir.
Render ücretsiz diski geçicidir: yeniden başlatma/yayın dosyayı silebilir.
Bu nedenle bulut WSGI başlangıcı `DATABASE_URL` olmadan çalışmayı reddeder.
Uzak veritabanı kesilirse boş yerel veritabanına geçilmez; hata döner.
Sunucu tarafındaki PostgreSQL bağlantısı TLS sertifika ve alan adı doğrulaması
kullanır. Supabase Connect ekranından pooler URL alınır; URL ve veritabanı
parolası yalnızca sunucunun gizli ortam ayarlarına konur. Tarayıcıya gönderilmez.
Gerekirse sağlayıcının CA sertifikasını `PGSSLROOTCERT` ile yapılandırın;
sertifika doğrulamasını kapatmayın. Docker sistem CA paketini kullanır.

Kayıtlar accounts, positions ve trades tablolarında tutulur. Parametreli SQL,
atomik işlemler ve PostgreSQL transaction advisory lock eşzamanlı yazmaları korur.
Bulut sürümü başlangıçta yalnızca eksik tabloları oluşturur; mevcut kayıtları silmez.

Mevcut Codespace'teki kayıtlar bu indirmeye dahil değildir. Taşıma öncesi işlemleri
durdurup `python3 -m web.backup KAYNAK.sqlite3 YEDEK.sqlite3` ile tutarlı SQLite
yedeği alın. Yedeği GitHub'a koymayın. PostgreSQL'e aktarım ayrı, kontrollü bir
adımdır: tüm hesap/pozisyon/işlem satırları, para birimleri, adetler, nakit ve
kâr/zarar toplamları bire bir doğrulanmalı; kimlik sırası son işlemden devam etmeli.
Kaynak yedek, aktarım ve geri yükleme testi doğrulanmadan silinmemeli.
Bulutta ayrıca düzenli `pg_dump` yedeği ve boş test veritabanına geri yükleme
provası gerekir; ücretsiz sağlayıcı yedeğinin var olduğu varsayılmaz.

## Yayına hazırlık ve kabul sırası

1. Önce bu değişiklikleri dal üzerinde gözden geçirin; otomatik yayın kapalı kalsın.
2. Kullanıcının yayın onayından sonra yalnızca Free planlarla hesap/hizmet kurun.
3. Render'da repo kökündeki Dockerfile kullanılır; uygulama `web/` içindedir.
   Başlangıç: Gunicorn factory `web.wsgi:create_app()`, 1 worker, 4 thread.
   Sağlık yolu `/api/health`. Sunucu ortamında `PAPER_PASSWORD_HASH` ve
   `DATABASE_URL` tanımlanır. `PAPER_LOCAL_HTTP` tanımlanmaz.
4. Önce ayrı test veritabanıyla gerçek PostgreSQL bağlantısı, TLS, alım/satım,
   eşzamanlı işlem ve rollback doğrulanır. Bu ortamda gerçek PostgreSQL sunucusu
   bulunmadığından bu canlı entegrasyon testi henüz yapılmadı.
5. Başka bir tarayıcıda girişsiz tüm özel yolların 401 verdiğini kontrol edin.
   Safari'de giriş/çıkış, ekran boyutu, yanlış parola, oturum süresi ve CSRF test edin.
6. Sanal işlem oluşturun; servisi yeniden başlatıp nakit, pozisyon ve geçmişin
   aynı kaldığını kontrol edin. Veritabanı kesilince yeni boş portföy oluşmamalı.
7. Yedek geri yükleme ve mevcut verinin aktarımı tamamlanınca MacBook'u kapatıp
   iPhone mobil internetinden deneyin. Başarılı doğrulamaları kullanıcıya sunun.

Bu hazırlık herhangi bir hizmeti başlatmaz veya uygulamayı yayınlamaz.
Gerçek emir gönderimi kapalıdır. Yahoo verisi erişimi/eskiliği bulutta ayrıca
kontrol edilir; demo kaynak her zaman açıkça etiketlenir.
