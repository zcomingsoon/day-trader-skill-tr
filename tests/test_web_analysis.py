import unittest
from unittest.mock import patch
from web.analysis import ema_series, explain
from web.market import chart


class Analysis(unittest.TestCase):
    def test_constant_and_linear_ema_macd(self):
        self.assertEqual(ema_series([10]*40,20), [10]*21)
        result = explain([{'close':10} for _ in range(220)],50)['indicators']
        self.assertEqual(result['macd'],0)
        self.assertEqual(result['histogram'],0)
        self.assertEqual(result['ema']['200'],10)
        self.assertAlmostEqual(ema_series(list(range(1,221)),20)[-1],210.5)

    def test_levels_exclude_current_bar_and_volume_uses_previous_twenty(self):
        points = [{'close':10,'low':9,'high':11,'volume':100} for _ in range(40)]
        points[-1] = {'close':15,'low':1,'high':20,'volume':200}
        result = explain(points,75)['indicators']
        self.assertEqual((result['support'],result['resistance']),(9,11))
        self.assertEqual(result['volume_ratio'],2)

    def test_missing_data_does_not_invent_indicators(self):
        result = chart('THYAO','BIST')
        indicators = result['analysis']['indicators']
        self.assertIsNone(indicators['volume'])
        self.assertIsNone(indicators['volume_ratio'])
        self.assertIsNone(indicators['ema']['200'])
        self.assertIn('DEMO',result['data_notice'])
        self.assertFalse(result['live_orders_enabled'])
        short = explain([{'close':10} for _ in range(21)],None)['indicators']
        self.assertIsNone(short['macd'])
        self.assertIsNone(short['signal'])

    def test_yahoo_preserves_volume_alignment_after_missing_close(self):
        import io, json
        data = {'chart':{'result':[{'meta':{'currency':'USD'},'timestamp':list(range(220)),
                'indicators':{'quote':[{'close':[None]+[10]*219,'high':[11]*220,
                                      'low':[9]*220,'volume':list(range(220))}]}}]}}
        with patch('web.market.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(data).encode())):
            result = chart('AAPL','ABD',source='yahoo')
        self.assertEqual(result['points'][0]['volume'],1)
        self.assertEqual(result['analysis']['indicators']['volume'],219)
        self.assertEqual(result['analysis']['indicators']['ema']['200'],10)
        self.assertIn('kesin gecikmesi doğrulanmadı',result['data_notice'])
