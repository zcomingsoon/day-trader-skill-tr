"""Deterministic indicators, using supplied closes only (no brokerage access)."""
import math


def ema(values, period):
    result = [None] * len(values)
    if len(values) >= period:
        result[period-1] = sum(values[:period]) / period
        for i in range(period, len(values)):
            result[i] = values[i] * (2/(period+1)) + result[i-1] * (1-2/(period+1))
    return result


def analyze(closes):
    def last(values):
        return round(values[-1], 4) if values and values[-1] is not None else None
    fast, slow = ema(closes, 12), ema(closes, 26)
    macd = [a-b for a,b in zip(fast,slow) if a is not None and b is not None]
    signal = ema(macd, 9)
    gains = [max(b-a, 0) for a,b in zip(closes,closes[1:])]
    losses = [max(a-b, 0) for a,b in zip(closes,closes[1:])]
    rsi = None
    if len(gains) >= 14:
        g,l = sum(gains[:14])/14, sum(losses[:14])/14
        for a,b in zip(gains[14:],losses[14:]):
            g,l = (g*13+a)/14, (l*13+b)/14
        rsi = 50 if g == l == 0 else 100 if l == 0 else 100-100/(1+g/l)
    middle = sum(closes[-20:])/20 if len(closes)>=20 else None
    deviation = math.sqrt(sum((x-middle)**2 for x in closes[-20:])/20) if middle is not None else None
    return {'rsi14': round(rsi,2) if rsi is not None else None,
            'sma20': middle, **{'ema'+str(n): last(ema(closes,n)) for n in (20,50,200)},
            'macd':last(macd), 'macd_signal':last(signal),
            'macd_histogram':round(macd[-1]-signal[-1],4) if signal and signal[-1] is not None else None,
            'bollinger_upper':middle+2*deviation if middle is not None else None,
            'bollinger_lower':middle-2*deviation if middle is not None else None,
            'bars':len(closes)}
