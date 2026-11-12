# Piyasa verisi ve kontrollü yayın

12 Kasım 2026 araştırması. Bu sürüm mevcut kişisel, giriş korumalı Yahoo
adaptörünü güçlendirir; lisanslı borsa akışı veya hizmet garantisi sağlamaz.
Ücretli abonelik, API anahtarı ve veritabanı şema değişikliği gerektirmez.

| Seçenek | Kısıt | Karar |
| --- | --- | --- |
| Yahoo Finance | Resmi chart API sözleşmesi/SLA yok; oran sınırlaması ve bağlantı kesintisi olabilir. BIST .IS verisi Yahoo listesinde 15 dakika gecikmeli. ABD gecikmesi borsaya göre değişir. | Mevcut kişisel kullanım adaptörü korundu; anlık veri iddiası yok. |
| Alpha Vantage Free | Çoğu veri kümesi için günlük 25 istek; anlık ve 15 dakika gecikmeli ABD verisi premium yetkilendirme gerektiriyor. | Sık yenilenen izleme ekranına uygun değil. |
| Twelve Data Basic | Ücretsiz kota ve kapsama/erişim hakları planla sınırlı; ABD dışı ticari gösterim ek onaya tabi. BIST ücretsiz anlık erişim varsayılmamalı. | Hesap açılmadı; geçiş yapılmadı. |
| Lisanslı BIST dağıtıcısı | Anlık veri için uygun dağıtıcı/son kullanıcı ve gösterim hakları gerekir. Gecikmeli veri de sınırsız yeniden dağıtım izni değildir. | Ücretli işlem başlatılmadı. |

Kaynaklar:
- https://help.yahoo.com/kb/finance/article-exchanges-data-delays-sln2310.html
- https://www.borsaistanbul.com/en/data
- https://www.borsaistanbul.com/en/data/data-dissemination/data-vendors-directory
- https://www.alphavantage.co/support/
- https://twelvedata.com/pricing
- https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage

## Veri sözleşmesi

Fiyat son mum kapanışıdır; işlem bazlı anlık fiyat değildir. `as_of` mumun
başlangıç etiketidir, son borsa işleminin zamanı değildir. `fetched_at` sunucunun
başarılı yanıt alma zamanıdır. 30 saniyelik en fazla 128 anahtarlı süreç önbelleği
bu zamanı değiştirmez. Hatalarda eski fiyat veya demo otomatik sunulmaz.
Günlük grafik iki yıllık veri ister (EMA200 için); eksik gösterge null olur.
Son mum değişebilir; göstergeler seçili döneme aittir. Bölünme/temettü düzeltmesi
ve kapanmış-mum sinyal motoru bu sürümün kapsamında değildir.

Sanal işlemler halen sunucuda yeniden 5 dakikalık veriyle fiyatlanır. Mevcut
15 dakika eskilik sınırı korunur; 15 dakika gecikmeli BIST mumları bu sınırı
geçebilir ve sanal işlem reddedilir. Bu sınırı gevşetmek bu değişikliğin parçası
değildir. Demo ile Yahoo hesapları ayrı kalır; eski demo portföyü taşınmaz.

## Yayın sırası

1. Değişiklik ayrı geliştirme dalında test edilir; üretim dalına doğrudan itilmez.
2. Render'da çalışan dal ve otomatik yayın ayarı doğrulanır. Mevcut Supabase
   hesabının nakit/pozisyon/işlem sayıları, sırları açığa çıkarmadan kaydedilir.
3. Test sonucu ve farklar incelendikten sonra çalışan servis yeni commit'e
   kontrollü geçirilir. DATABASE_URL ve parola ayarları değiştirilmez.
4. Sağlık, giriş, THYAO/AAPL kaynak ve zaman etiketleri, kaynak kesintisi ve
   iPhone görünümü kontrol edilir. Portföy sayıları tekrar karşılaştırılır.
5. Hata varsa Render önceki çalışan commit'e döndürülür; veritabanı silinmez.

Canlı Render/Supabase kabul testi ayrıca doğrulanmadan tamamlandı sayılmaz.
