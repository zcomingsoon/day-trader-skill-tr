"""Transactional long-only simulation ledger; amounts stored in integer cents."""
import datetime
import sqlite3
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def cents(value):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n <= 0:
            raise ValueError('Tutar pozitif ve sonlu olmalı.')
        return int((n * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError):
        raise ValueError('Geçersiz tutar.')


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, cash INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS positions (account TEXT, symbol TEXT, qty INTEGER, cost INTEGER, stop INTEGER, PRIMARY KEY(account,symbol));
            CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, account TEXT, symbol TEXT, side TEXT, qty INTEGER, price INTEGER, risk INTEGER, pnl INTEGER, at TEXT);
            ''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def snapshot(self, source, currency):
        account = self.account(source, currency)
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO accounts VALUES (?,?)', (account, 10000000))
            cash = db.execute('SELECT cash FROM accounts WHERE id=?', (account,)).fetchone()[0]
            positions = [dict(zip(('symbol','qty','cost','stop'), row)) for row in db.execute('SELECT symbol,qty,cost,stop FROM positions WHERE account=?', (account,))]
            realized_pnl = db.execute('SELECT COALESCE(SUM(pnl),0) FROM trades WHERE account=?', (account,)).fetchone()[0]
            trades = [dict(zip(('id','symbol','side','qty','price','risk','pnl','at'), row)) for row in db.execute('SELECT id,symbol,side,qty,price,risk,pnl,at FROM trades WHERE account=? ORDER BY id DESC LIMIT 100', (account,))]
        return dict(cash=cash, positions=positions, trades=trades, realized_pnl=realized_pnl, currency=currency, source=source, live_orders_enabled=False)

    @staticmethod
    def account(source, currency):
        if source not in ('demo', 'yahoo') or currency not in ('TRY', 'USD'):
            raise ValueError('Geçersiz hesap.')
        return source + ':' + currency

    def trade(self, quote, side, qty, stop=None):
        if side not in ('buy', 'sell') or type(qty) is not int or not 1 <= qty <= 1000000:
            raise ValueError('Yön ve tam adet (1-1000000) gerekli.')
        account = self.account(quote['source'], quote['currency'])
        price = cents(quote['price'])
        if price <= 0:
            raise ValueError('Geçersiz fiyat.')
        if quote['source'] == 'yahoo':
            age = datetime.datetime.now(datetime.timezone.utc).timestamp() - quote['as_of']
            if not -60 <= age <= 900:
                raise ValueError('Fiyat 15 dakikadan eski; sanal işlem engellendi.')
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        day = now[:10]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO accounts VALUES (?,?)', (account, 10000000))
            cash = db.execute('SELECT cash FROM accounts WHERE id=?', (account,)).fetchone()[0]
            old = db.execute('SELECT qty,cost,stop FROM positions WHERE account=? AND symbol=?', (account,quote['symbol'])).fetchone()
            risk, pnl = 0, 0
            if side == 'buy':
                stop = cents(stop)
                if not 0 < stop < price:
                    raise ValueError('Zarar durdurma fiyatın altında olmalı.')
                if old:
                    raise ValueError('Aynı pozisyona ekleme ilk sürümde kapalı.')
                value, risk = price*qty, (price-stop)*qty
                equity = cash + db.execute('SELECT COALESCE(SUM(cost),0) FROM positions WHERE account=?',(account,)).fetchone()[0]
                used, count = db.execute("SELECT COALESCE(SUM(risk),0),COUNT(*) FROM trades WHERE account=? AND side='buy' AND substr(at,1,10)=?",(account,day)).fetchone()
                open_risk = db.execute('SELECT COALESCE(SUM(cost-stop*qty),0) FROM positions WHERE account=?',(account,)).fetchone()[0]
                realized = db.execute('SELECT COALESCE(SUM(pnl),0) FROM trades WHERE account=? AND substr(at,1,10)=?',(account,day)).fetchone()[0]
                if value > cash or value > equity*.25:
                    raise ValueError('Nakit veya %25 pozisyon limiti aşıldı.')
                if risk > equity*.01 or used+risk > equity*.03 or open_risk+risk > equity*.05 or realized <= -equity*.03 or count >= 10:
                    raise ValueError('İşlem veya günlük risk limiti aşıldı.')
                db.execute('INSERT INTO positions VALUES (?,?,?,?,?)',(account,quote['symbol'],qty,value,stop))
                cash -= value
            else:
                if not old or qty > old[0]:
                    raise ValueError('Eldeki adetten fazla satış yapılamaz.')
                removed = old[1] if qty == old[0] else old[1]*qty//old[0]
                pnl = qty*price-removed
                if qty == old[0]:
                    db.execute('DELETE FROM positions WHERE account=? AND symbol=?',(account,quote['symbol']))
                else:
                    db.execute('UPDATE positions SET qty=?,cost=? WHERE account=? AND symbol=?',(old[0]-qty,old[1]-removed,account,quote['symbol']))
                cash += price*qty
            db.execute('UPDATE accounts SET cash=? WHERE id=?',(cash,account))
            db.execute('INSERT INTO trades(account,symbol,side,qty,price,risk,pnl,at) VALUES (?,?,?,?,?,?,?,?)',(account,quote['symbol'],side,qty,price,risk,pnl,now))
        return self.snapshot(quote['source'],quote['currency'])
