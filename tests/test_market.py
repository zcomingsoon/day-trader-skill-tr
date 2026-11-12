import json
import unittest
from unittest.mock import patch, MagicMock
from web import market
from web.indicators import analyze


class Indicators(unittest.TestCase):
    def test_flat_series_and_warmup(self):
        a = analyze([100.0]*250)
        self.assertEqual(a['rsi14'], 50)
        for key in ('ema20','ema50','ema200','sma20','bollinger_upper','bollinger_lower'):
            self.assertAlmostEqual(a[key],100)
        self.assertEqual(a['macd'],0)
        self.assertEqual(a['macd_histogram'],0)
        self.assertIsNone(analyze([1.0]*21)['ema200'])
        self.assertIsNone(analyze([1.0]*30)['macd_signal'])

    def test_rising_series(self):
        a = analyze(list(range(1,251)))
        self.assertEqual(a['rsi14'],100)
        self.assertAlmostEqual(a['ema20'],240.5)
        self.assertAlmostEqual(a['macd'],7)
        self.assertAlmostEqual(a['macd_signal'],7)


class Market(unittest.TestCase):
    def setUp(self):
        market._CACHE.clear()

    def payload(self, symbol='THYAO.IS', currency='TRY'):
        return {'chart':{'result':[{'meta':{'symbol':symbol,'currency':currency},
                 'timestamp':list(range(1700000000,1700000000+30*300,300)),
                 'indicators':{'quote':[{'close':[100.0]*30}]}}]}}

    def fetch(self, payload):
        response = MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(payload).encode()
        return patch('web.market.urllib.request.urlopen',return_value=response)

    def test_labels_cache_and_no_demo_fallback(self):
        with self.fetch(self.payload()) as fetch:
            q=market.chart('THYAO','BIST','intraday','yahoo')
            self.assertFalse(q['is_demo'])
            self.assertEqual(q['delay_minutes'],15)
            self.assertTrue(q['stale'])
            self.assertFalse(q['live_orders_enabled'])
            self.assertTrue(market.chart('THYAO','BIST','intraday','yahoo')['cached'])
            self.assertEqual(fetch.call_count,1)
        market._CACHE.clear()
        with patch('web.market.urllib.request.urlopen',side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                market.chart('THYAO','BIST',source='yahoo')

    def test_wrong_currency_symbol_and_order_rejected(self):
        for payload in [self.payload(currency='USD'),self.payload(symbol='AAPL')]:
            with self.fetch(payload), self.assertRaises(ValueError):
                market.chart('THYAO','BIST',source='yahoo')
        payload=self.payload()
        payload['chart']['result'][0]['timestamp'].reverse()
        with self.fetch(payload), self.assertRaises(ValueError):
            market.chart('THYAO','BIST',source='yahoo')

    def test_demo_explicit(self):
        q=market.chart('THYAO','BIST')
        self.assertTrue(q['is_demo'])
        self.assertEqual(q['source'],'demo')
