"""Read-only market adapter. No brokerage dependencies."""
import datetime
import importlib.util
import json
import math
from pathlib import Path
import re
import urllib.request

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
    currency = 'TRY' if market == 'BIST' else 'USD'
    if source == 'demo':
        base = 280 if market == 'BIST' else 200
        # Fixed illustrative data; never presented as current market data.
        end = datetime.datetime(2026, 10, 19, 14, 0, tzinfo=datetime.timezone.utc).timestamp()
        step = 86400 if period == 'daily' else 300
        points = [{'time': int(end - (79-i)*step), 'close': round(base + i*.15 + math.sin(i/4)*2, 2)} for i in range(80)]
    else:
        interval, rng = ('1d', '6mo') if period == 'daily' else ('5m', '5d')
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s' % (symbol, rng, interval)
        req = urllib.request.Request(url, headers={'User-Agent': scan.UA})
        with urllib.request.urlopen(req, timeout=15) as response:
            doc = json.load(response)
        results = doc.get('chart', {}).get('result')
        if not results:
            raise ValueError('Piyasa verisi bulunamadı.')
        series = scan.series_from_result(results[0])
        if series['meta'].get('currency') != currency:
            raise ValueError('Verinin para birimi hesapla eşleşmiyor.')
        points = [{'time': t, 'close': float(c)} for t, c in zip(series['t'], series['c'])
                  if c is not None and math.isfinite(c) and c > 0]
    if len(points) < 21:
        raise ValueError('Analiz için yeterli veri yok.')
    closes = [p['close'] for p in points]
    return {'symbol': symbol, 'market': market, 'currency': currency, 'source': source,
            'period': period, 'points': points, 'price': closes[-1],
            'as_of': points[-1]['time'], 'change_pct': round((closes[-1]/closes[-2]-1)*100, 2),
            'sma20': round(sum(closes[-20:])/20, 2), 'rsi14': scan.rsi(closes),
            'live_orders_enabled': False}
