"""Deterministic Turkish explanations; no external model or paid service."""


def ema_series(values, period):
    if len(values) < period:
        return []
    result = [sum(values[:period]) / period]
    for value in values[period:]:
        result.append(result[-1] + 2 / (period + 1) * (value - result[-1]))
    return result


def explain(points, rsi):
    closes = [p['close'] for p in points]
    price = closes[-1]
    def fmt(value):
        return 'veri yetersiz' if value is None else f'{value:.4f}'
    emas = {str(n): (ema_series(closes, n) or [None])[-1] for n in (20, 50, 200)}
    fast, slow = ema_series(closes, 12), ema_series(closes, 26)
    macds = [a-b for a,b in zip(fast[14:], slow)]
    signals = ema_series(macds, 9)
    macd = macds[-1] if macds else None
    signal = signals[-1] if signals else None
    histogram = macd-signal if signal is not None else None
    # Exclude the current bar: levels describe the preceding 20 bars.
    prior = points[-21:-1]
    support = min(p.get('low') or p['close'] for p in prior)
    resistance = max(p.get('high') or p['close'] for p in prior)
    full_range = all(p.get('low') is not None and p.get('high') is not None for p in prior)
    volumes = [p.get('volume') for p in prior]
    volume = points[-1].get('volume')
    average = sum(volumes)/20 if all(v is not None for v in volumes) else None
    ratio = volume/average if volume is not None and average and average > 0 else None
    trend = 'değerlendirilemiyor'
    if emas['50'] is not None:
        trend = 'karışık'
        if price > emas['20'] > emas['50']:
            trend = 'yukarı eğilimli'
        elif price < emas['20'] < emas['50']:
            trend = 'aşağı eğilimli'
    lines = [f'Genel görünüm: {trend}. Son mum kapanışı {fmt(price)}.',
             'EMA 20 / 50 / 200: ' + ' / '.join(fmt(emas[str(n)]) for n in (20,50,200)) + '.']
    zone = 'değerlendirilemiyor' if rsi is None else 'aşırı alım bölgesinde; geri çekilme riski izlenmeli' if rsi >= 70 else 'aşırı satım bölgesinde; dönüş garanti değildir' if rsi <= 30 else '30–70 aralığında'
    lines.append(f'RSI 14: {fmt(rsi)}; {zone}.')
    momentum = 'veri yetersiz' if histogram is None else 'MACD sinyalinin üzerinde' if histogram > 0 else 'MACD sinyalinin altında' if histogram < 0 else 'MACD ve sinyal eşit'
    lines.append(f'MACD (12,26,9): {fmt(macd)}; sinyal {fmt(signal)}; histogram {fmt(histogram)}. Momentum: {momentum}.')
    lines.append(f'Önceki 20 mumun aralığı: destek {fmt(support)}, direnç {fmt(resistance)}. ' + ('En düşük/en yüksek fiyatlar kullanıldı.' if full_range else 'Eksik yüksek/düşük verisi nedeniyle kapanış bazlı yaklaşık seviyeler kullanıldı.'))
    lines.append(f'Hacim: {fmt(volume)}; önceki 20 mum ortalaması {fmt(average)}; oran {fmt(ratio)}. ' + ('Hacim teyidi değerlendirilemiyor.' if ratio is None else 'Oran 1 üzerinde olduğunda son mum hacmi ortalamanın üzerindedir.'))
    lines.append('Olumlu senaryo: direnç üzerinde kapanış ve artan hacim görünümü güçlendirebilir. Risk senaryosu: destek altında kapanış görünümü zayıflatabilir. Bunlar koşullu senaryolardır; fiyatın bu seviyelere ulaşacağı öngörülmez.')
    lines.append('Göstergeler gecikmeli ve birbiriyle çelişkili olabilir. Son mum tamamlanmamış olabilir; özellikle gün içi hacim kıyaslaması saat etkisini düzeltmez. Eğitim ve sanal işlem amaçlıdır; kesin al-sat veya yatırım tavsiyesi değildir.')
    return {'method':'rules', 'title':'Kurallı Türkçe analiz · ücretsiz', 'paragraphs':lines,
            'indicators':{'ema':emas,'macd':macd,'signal':signal,'histogram':histogram,'support':support,'resistance':resistance,'volume':volume,'volume_average20':average,'volume_ratio':ratio}}
