"""Read-only market adapter. No brokerage dependencies."""
import datetime
import importlib.util
import json
import math
from pathlib import Path
import re
import urllib.request
import time
import threading
from collections import OrderedDict
from .indicators import analyze
from .analysis import explain

_CACHE = OrderedDict()
_LOCK = threading.Lock()

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('legacy_scan', ROOT / 'trader-scanner/scan.py')
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def normalize(symbol, market):
    if market not in ('BIST', 'ABD'):
        raise ValueError('Piyasa BIST veya ABD olmalı.')
    symbol = str(symbol).strip().upper()
    if market == 'BIST':
        symbol = symbol[:-3] if symbol.endswith('.IS') else symbol
        if not re.fullmatch(r'[A-Z]{4,6}', symbol):
            raise ValueError('Geçersiz BIST sembolü.')
        return symbol + '.IS'
    if not re.fullmatch(r'[A-Z]{1,5}(?:[.-][A-Z])?', symbol):
        raise ValueError('Geçersiz ABD sembolü.')
    return symbol.replace('.', '-')


def chart(symbol, market, period='daily', source='demo'):
    symbol = normalize(symbol, market)
    if period not in ('daily', 'intraday') or source not in ('demo', 'yahoo'):
        raise ValueError('Geçersiz dönem veya veri kaynağı.')
    now = int(time.time())
    key = (symbol, market, period, source)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached['fetched_at'] < 30:
            return {**cached, 'cached': True}
    currency = 'TRY' if market == 'BIST' else 'USD'
    if source == 'demo':
        base = 280 if market == 'BIST' else 200
        # Fixed illustrative data; never presented as current market data.
        end = datetime.datetime(2026, 10, 19, 14, 0, tzinfo=datetime.timezone.utc).timestamp()
        step = 86400 if period == 'daily' else 300
        points = [{'time': int(end - (79-i)*step), 'close': round(base + i*.15 + math.sin(i/4)*2, 2)} for i in range(80)]
    else:
        interval, rng = ('1d', '2y') if period == 'daily' else ('5m', '5d')
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s' % (symbol, rng, interval)
        req = urllib.request.Request(url, headers={'User-Agent': scan.UA})
        with urllib.request.urlopen(req, timeout=15) as response:
            doc = json.load(response)
        results = doc.get('chart', {}).get('result')
        if not results:
            raise ValueError('Piyasa verisi bulunamadı.')
        series = scan.series_from_result(results[0])
        if series['meta'].get('symbol') != symbol:
            raise ValueError('Sağlayıcının sembolü istekle eşleşmiyor.')
        if series['meta'].get('currency') != currency:
            raise ValueError('Verinin para birimi hesapla eşleşmiyor.')
        def number_at(key, i):
            values = series.get(key)
            value = values[i] if values and i < len(values) else None
            return float(value) if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else None
        points = [{'time': t, 'close': float(c), 'high': number_at('h', i),
                   'low': number_at('l', i), 'volume': number_at('v', i)}
                  for i, (t, c) in enumerate(zip(series['t'], series['c']))
                  if isinstance(t, (int, float)) and 0 < t <= now + 60
                  and isinstance(c, (int, float)) and math.isfinite(c) and c > 0]
        if any(a['time'] >= b['time'] for a,b in zip(points, points[1:])):
            raise ValueError('Sağlayıcının zaman dizisi geçersiz.')
    if len(points) < 21:
        raise ValueError('Analiz için yeterli veri yok.')
    closes = [p['close'] for p in points]
    result = {'symbol': symbol, 'market': market, 'currency': currency, 'source': source,
            'period': period, 'points': points, 'price': closes[-1],
            'as_of': points[-1]['time'], 'change_pct': round((closes[-1]/closes[-2]-1)*100, 2),
            'live_orders_enabled': False}
    indicators = analyze(closes)
    result.update(sma20=indicators['sma20'], rsi14=indicators['rsi14'], indicators=indicators,
                  fetched_at=int(time.time()), cached=False, is_demo=source == 'demo',
                  delay_minutes=15 if market == 'BIST' and source == 'yahoo' else None,
                  delay_label=('Örnek veri · piyasa fiyatı değil' if source == 'demo' else
                               '15 dakika gecikmeli · anlık lisans yok' if market == 'BIST' else
                               'Gecikme borsaya göre değişir · anlık garanti yok'),
                  source_label='Demo' if source == 'demo' else 'Yahoo Finance · resmi olmayan uç nokta',
                  price_kind='Son mum kapanışı',
                  stale=source != 'demo' and now-points[-1]['time'] > (900 if period == 'intraday' else 3*86400))
    result['analysis'] = explain(points, indicators['rsi14'], indicators)
    result['data_notice'] = result['delay_label']
    with _LOCK:
        _CACHE[key] = result
        _CACHE.move_to_end(key)
        while len(_CACHE) > 128:
            _CACHE.popitem(last=False)
    return result
