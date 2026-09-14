import os
import sys
from pathlib import Path
from datetime import datetime, timezone

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test-token')
os.environ.setdefault('TELEGRAM_CHAT_ID', 'test-chat')
os.environ.setdefault('ALLOW_MONGOMOCK', 'true')
os.environ.setdefault('JWT_SECRET_KEY', 'local-test-only-not-production-32-chars-minimum')
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'market-backend'))
sys.path.insert(0, os.path.dirname(__file__))

import telegram_reports_bot as bot


def main():
    inventory = bot.render_inventory_pdf({
        'audit_no': 'AUD-TEST-00001', 'created_at': datetime.now(timezone.utc),
        'branch': 'ميني ماركت الفنية', 'actor_name': 'اختبار', 'notes': '',
        'rows': [
            {'line_no': i, 'barcode': f'628000{i:04d}', 'name': 'منتج عربي ' + str(i), 'unit': 'قطعة',
             'actual_quantity': 10 + i, 'system_quantity': 11 + i, 'unit_cost': 100.5}
            for i in range(1, 80)
        ], 'total_items': 79, 'total_actual': sum(10 + i for i in range(1, 80)),
        'total_system': sum(11 + i for i in range(1, 80)),
    })
    assert inventory.startswith(b'%PDF-') and len(inventory) > 10000
    Path('/tmp/telegram-inventory-test.pdf').write_bytes(inventory)
    purchases = bot.build_purchase_pdf([], 'اختبار المشتريات')
    assert purchases.startswith(b'%PDF-')
    expenses = bot.build_expense_pdf([], 'اختبار المصروفات')
    assert expenses.startswith(b'%PDF-')
    statement = bot.build_statement_pdf('اختبار كشف الحساب', [], {})
    assert statement.startswith(b'%PDF-')
    print('PASS telegram import and PDF generators', len(inventory), len(purchases), len(expenses), len(statement))


if __name__ == '__main__':
    main()
