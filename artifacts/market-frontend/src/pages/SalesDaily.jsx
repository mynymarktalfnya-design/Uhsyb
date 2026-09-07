import React, { useEffect, useMemo, useState } from 'react';
import { Card, CardContent } from '../components/ui/card';
import {
  Banknote, Building2, Calendar, CreditCard, Receipt, RefreshCw,
  Smartphone, TrendingUp,
} from 'lucide-react';
import api from '../lib/api';

const fmt = (n) => new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(Number(n) || 0);
const money = (n) => `${fmt(n)} ر.ي`;
const PAYMENT_LABELS = {
  cash: 'نقداً', credit: 'آجل', jaib: 'جيب', fluusak: 'فلوسك',
  hasib: 'حاسب', banki: 'بنكي', bank_transfer: 'تحويل بنكي',
  transfer: 'تحويل بنكي', card: 'بطاقة',
};

const businessToday = () => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Aden',
}).format(new Date());

const SummaryCard = ({ label, value, count, icon: Icon, color, testId }) => (
  <Card className="overflow-hidden border-0 shadow-md">
    <div className={`bg-gradient-to-br ${color} p-4 text-white`}>
      <Icon className="mb-2 h-6 w-6 opacity-90" />
      <p className="text-xs text-white/80">{label}</p>
      <p className="text-xl font-extrabold" data-testid={testId}>{money(value)}</p>
      {count !== undefined && <p className="mt-1 text-[10px] text-white/65">{fmt(count)} فاتورة</p>}
    </div>
  </Card>
);

const SalesDaily = () => {
  const [date, setDate] = useState(businessToday);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = () => {
      setLoading(true);
      api.get('/dashboard/cashier-report', { params: { date } })
        .then((r) => alive && setReport(r.data))
        .catch(() => alive && setReport(null))
        .finally(() => alive && setLoading(false));
    };
    load();
    const refreshId = setInterval(load, 30000);
    return () => { alive = false; clearInterval(refreshId); };
  }, [date]);

  const sales = report?.sales || {};
  const returns = report?.returns || {};
  const invoices = report?.invoices || [];
  const returnRows = report?.return_rows || [];
  const cards = useMemo(() => [
    { label: 'إجمالي المبيعات اليومية', value: sales.total, count: sales.invoice_count, icon: Receipt, color: 'from-emerald-500 to-teal-600', testId: 'cashier-total-sales' },
    { label: 'المبيعات النقدية', value: sales.cash, count: sales.cash_invoices, icon: Banknote, color: 'from-blue-500 to-indigo-600', testId: 'cashier-cash-sales' },
    { label: 'مبيعات الأجل', value: sales.credit, count: sales.credit_invoices, icon: TrendingUp, color: 'from-amber-500 to-orange-600', testId: 'cashier-credit-sales' },
    { label: 'مبيعات المحافظ الإلكترونية', value: sales.wallet, count: sales.wallet_invoices, icon: Smartphone, color: 'from-violet-500 to-purple-600', testId: 'cashier-wallet-sales' },
    { label: 'مبيعات التحويل البنكي', value: sales.bank_transfer, count: sales.bank_transfer_invoices, icon: Building2, color: 'from-indigo-500 to-indigo-700', testId: 'cashier-bank-sales' },
    { label: 'مبيعات البطاقات', value: sales.card, count: sales.card_invoices, icon: CreditCard, color: 'from-slate-600 to-slate-800', testId: 'cashier-card-sales' },
    { label: 'إجمالي المرتجعات اليومية', value: returns.total, count: returns.count, icon: RefreshCw, color: 'from-rose-500 to-pink-600', testId: 'cashier-returns' },
    { label: 'صافي المبيعات اليومية', value: report?.net_sales, icon: TrendingUp, color: 'from-green-600 to-emerald-700', testId: 'cashier-net-sales' },
  ], [report, sales, returns]);

  return (
    <div className="space-y-6 p-6 lg:p-8" dir="rtl" data-testid="cashier-daily-report">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">تقرير الكاشير اليومي</h1>
          <p className="mt-1 text-sm text-slate-500">
            {report?.cashier?.name || '—'} — الأرقام من سجل الفواتير والمرتجعات المعتمدة
          </p>
        </div>
        <label className="flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm">
          <Calendar className="h-4 w-4 text-slate-500" />
          <span className="text-slate-500">تاريخ التقرير</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="font-semibold outline-none" data-testid="cashier-report-date" />
        </label>
      </div>

      {loading && !report ? (
        <div className="rounded-xl border border-dashed p-12 text-center text-slate-400">جاري تحميل التقرير...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {cards.map((card) => <SummaryCard key={card.label} {...card} />)}
          </div>

          <Card className="border-2 border-slate-200">
            <CardContent className="p-5">
              <h2 className="mb-4 text-lg font-bold text-slate-900">ملخص عدد الفواتير</h2>
              <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-5">
                {[
                  ['النقد', sales.cash_invoices],
                  ['الآجل', sales.credit_invoices],
                  ['المحافظ', sales.wallet_invoices],
                  ['التحويل', sales.bank_transfer_invoices],
                  ['البطاقات', sales.card_invoices],
                ].map(([label, count]) => (
                  <div key={label} className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs text-slate-500">{label}</p>
                    <p className="mt-1 text-2xl font-extrabold text-slate-800">{fmt(count)}</p>
                  </div>
                ))}
              </div>
              <div className="mt-5 space-y-2 border-t pt-4 text-sm">
                <div className="flex justify-between"><span>إجمالي المبيعات قبل المرتجعات</span><strong className="text-emerald-700">{money(sales.total)}</strong></div>
                <div className="flex justify-between"><span>إجمالي المرتجعات المعتمدة</span><strong className="text-rose-600">− {money(returns.total)}</strong></div>
                <div className="flex justify-between border-t pt-2 text-base"><strong>صافي المبيعات بعد المرتجعات</strong><strong className="text-green-700">{money(report?.net_sales)}</strong></div>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Card className="overflow-hidden">
              <div className="border-b bg-slate-50 p-4"><h2 className="font-bold">فواتير البيع ({fmt(sales.invoice_count)})</h2></div>
              <div className="max-h-96 overflow-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-right text-xs text-slate-500"><tr><th className="p-3">الفاتورة</th><th className="p-3">طريقة الدفع</th><th className="p-3">الإجمالي</th></tr></thead>
                  <tbody>
                    {invoices.length === 0 && <tr><td colSpan="3" className="p-8 text-center text-slate-400">لا توجد فواتير في هذا اليوم</td></tr>}
                    {invoices.map((invoice) => (
                      <tr key={invoice.id} className="border-t">
                        <td className="p-3 font-mono text-amber-700">{invoice.invoice_no}</td>
                        <td className="p-3 text-slate-600">{PAYMENT_LABELS[invoice.payment_method] || invoice.payment_method}</td>
                        <td className="p-3 font-bold text-emerald-700">{money(invoice.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card className="overflow-hidden">
              <div className="border-b bg-rose-50 p-4"><h2 className="font-bold text-rose-900">المرتجعات المعتمدة ({fmt(returns.count)})</h2></div>
              <div className="max-h-96 overflow-auto">
                <table className="w-full text-sm">
                  <thead className="bg-rose-50/50 text-right text-xs text-slate-500"><tr><th className="p-3">المرتجع</th><th className="p-3">نوع الاسترداد</th><th className="p-3">القيمة</th></tr></thead>
                  <tbody>
                    {returnRows.length === 0 && <tr><td colSpan="3" className="p-8 text-center text-slate-400">لا توجد مرتجعات معتمدة</td></tr>}
                    {returnRows.map((item) => (
                      <tr key={item.id} className="border-t">
                        <td className="p-3 font-mono text-rose-700">{item.return_no || item.id}</td>
                        <td className="p-3 text-slate-600">{PAYMENT_LABELS[item.return_type] || item.return_type || '—'}</td>
                        <td className="p-3 font-bold text-rose-600">− {money(item.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
};

export default SalesDaily;