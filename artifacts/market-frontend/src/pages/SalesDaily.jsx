import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Calendar, TrendingUp, Receipt, DollarSign, RefreshCw, TrendingDown } from 'lucide-react';
import api from '../lib/api';

const fmt = (n) => new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(n || 0);
const money = (n) => `${fmt(n)} ر.ي`;

const PAYMENT_LABELS = {
  cash: 'نقداً', jaib: 'جيب', fluusak: 'فلوسك', hasib: 'حاسب',
  banki: 'بنكي', bank_transfer: 'تحويل', credit: 'آجل',
};
const localDate = () => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

const SalesDaily = () => {
  const today = localDate();
  const [sales, setSales] = useState([]);
  const [returns, setReturns] = useState([]);
  const [date, setDate] = useState(today);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const p1 = api.get('/sales', {
      params: { date_from: date + 'T00:00:00', date_to: date + 'T23:59:59', limit: 500 },
    }).then((r) => setSales(r.data)).catch(() => setSales([]));

    const p2 = api.get('/sales-returns', {
      params: { status: 'approved', date_from: `${date}T00:00:00+00:00`, date_to: `${date}T23:59:59.999+00:00`, limit: 500 },
    }).then((r) => setReturns(Array.isArray(r.data) ? r.data : r.data?.items || []))
      .catch(() => setReturns([]));

    Promise.all([p1, p2]).finally(() => setLoading(false));
  }, [date]);

  const grossTotal = sales.reduce((s, x) => s + Number(x.total || 0), 0);
  const returnsTotal = returns.reduce((s, x) => s + Number(x.total || 0), 0);
  const netTotal = grossTotal - returnsTotal;
  const invoiceCount = sales.length;
  const returnsCount = returns.length;

  return (
    <div className="p-6 lg:p-8" dir="rtl" data-testid="sales-daily-page">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-1">المبيعات اليومية</h1>
          <p className="text-slate-500">تفاصيل مبيعات وصافي اليوم</p>
        </div>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="border rounded-md px-3 py-2"
          data-testid="sales-daily-date-input"
        />
      </div>

      {/* بطاقات الملخص المالي */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card className="overflow-hidden border-0 shadow-lg">
          <div className="bg-gradient-to-br from-emerald-500 to-teal-600 p-5 text-white">
            <DollarSign className="w-7 h-7 mb-3 opacity-90" />
            <p className="text-white/80 text-sm">إجمالي المبيعات</p>
            <p className="text-2xl font-bold" data-testid="kpi-gross-sales">{loading ? '...' : money(grossTotal)}</p>
            <p className="text-white/60 text-xs mt-1">{invoiceCount} فاتورة</p>
          </div>
        </Card>

        <Card className="overflow-hidden border-0 shadow-lg">
          <div className="bg-gradient-to-br from-rose-500 to-pink-600 p-5 text-white">
            <RefreshCw className="w-7 h-7 mb-3 opacity-90" />
            <p className="text-white/80 text-sm">إجمالي المرتجعات</p>
            <p className="text-2xl font-bold" data-testid="kpi-returns">{loading ? '...' : money(returnsTotal)}</p>
            <p className="text-white/60 text-xs mt-1">{returnsCount} مرتجع</p>
          </div>
        </Card>

        <Card className="overflow-hidden border-0 shadow-lg">
          <div className={`bg-gradient-to-br p-5 text-white ${netTotal >= 0 ? 'from-green-600 to-emerald-700' : 'from-red-600 to-rose-700'}`}>
            <TrendingUp className="w-7 h-7 mb-3 opacity-90" />
            <p className="text-white/80 text-sm">صافي المبيعات</p>
            <p className="text-2xl font-bold" data-testid="kpi-net-sales">{loading ? '...' : money(netTotal)}</p>
            <p className="text-white/60 text-xs mt-1">= المبيعات - المرتجعات</p>
          </div>
        </Card>

        <Card className="overflow-hidden border-0 shadow-lg">
          <div className="bg-gradient-to-br from-amber-500 to-orange-600 p-5 text-white">
            <Receipt className="w-7 h-7 mb-3 opacity-90" />
            <p className="text-white/80 text-sm">عدد الفواتير</p>
            <p className="text-2xl font-bold">{loading ? '...' : invoiceCount}</p>
            <p className="text-white/60 text-xs mt-1">{returnsCount > 0 ? `${returnsCount} مرتجع` : 'لا مرتجعات'}</p>
          </div>
        </Card>
      </div>

      {/* جدول المبيعات */}
      <Card className="overflow-hidden mb-6">
        <div className="p-4 border-b bg-slate-50 flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-emerald-600" />
          <h2 className="font-bold text-slate-900">فواتير البيع</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-700">
              <tr>
                <th className="px-4 py-3 text-right">الوقت</th>
                <th className="px-4 py-3 text-right">رقم الفاتورة</th>
                <th className="px-4 py-3 text-right">الإجمالي</th>
                <th className="px-4 py-3 text-right">طريقة الدفع</th>
              </tr>
            </thead>
            <tbody>
              {sales.length === 0 && (
                <tr><td colSpan="4" className="text-center py-12 text-slate-400">لا مبيعات في هذا اليوم</td></tr>
              )}
              {sales.map((s) => (
                <tr key={s.id} className="border-t hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-600">{new Date(s.created_at).toLocaleTimeString('ar-EG')}</td>
                  <td className="px-4 py-3 font-medium text-amber-700">{s.invoice_no}</td>
                  <td className="px-4 py-3 font-bold text-emerald-600">{money(s.total)}</td>
                  <td className="px-4 py-3 text-slate-600">{PAYMENT_LABELS[s.payment_method] || s.payment_method}</td>
                </tr>
              ))}
            </tbody>
            {sales.length > 0 && (
              <tfoot className="bg-emerald-50 font-bold text-emerald-800 border-t-2 border-emerald-200">
                <tr>
                  <td className="px-4 py-3" colSpan="2">إجمالي المبيعات</td>
                  <td className="px-4 py-3 text-emerald-700">{money(grossTotal)}</td>
                  <td className="px-4 py-3"></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Card>

      {/* جدول المرتجعات */}
      {(returnsCount > 0 || !loading) && (
        <Card className="overflow-hidden mb-6">
          <div className="p-4 border-b bg-rose-50 flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-rose-600" />
            <h2 className="font-bold text-rose-900">مرتجعات اليوم</h2>
            {returnsCount > 0 && (
              <span className="mr-auto bg-rose-200 text-rose-800 text-xs font-bold px-2 py-0.5 rounded-full">
                {returnsCount} مرتجع
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-700">
                <tr>
                  <th className="px-4 py-3 text-right">الوقت</th>
                  <th className="px-4 py-3 text-right">رقم المرتجع</th>
                  <th className="px-4 py-3 text-right">قيمة المرتجع</th>
                  <th className="px-4 py-3 text-right">نوع الإرجاع</th>
                </tr>
              </thead>
              <tbody>
                {returnsCount === 0 && (
                  <tr><td colSpan="4" className="text-center py-8 text-slate-400">لا مرتجعات في هذا اليوم</td></tr>
                )}
                {returns.map((r) => (
                  <tr key={r.id} className="border-t hover:bg-rose-50">
                    <td className="px-4 py-3 text-slate-600">{new Date(r.created_at).toLocaleTimeString('ar-EG')}</td>
                    <td className="px-4 py-3 font-medium text-rose-700">{r.return_no || r.id?.slice(-6)}</td>
                    <td className="px-4 py-3 font-bold text-rose-600">- {money(r.total)}</td>
                    <td className="px-4 py-3 text-slate-600">{PAYMENT_LABELS[r.return_type] || r.return_type || '—'}</td>
                  </tr>
                ))}
              </tbody>
              {returnsCount > 0 && (
                <tfoot className="bg-rose-50 font-bold text-rose-800 border-t-2 border-rose-200">
                  <tr>
                    <td className="px-4 py-3" colSpan="2">إجمالي المرتجعات</td>
                    <td className="px-4 py-3 text-rose-700">- {money(returnsTotal)}</td>
                    <td className="px-4 py-3"></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </Card>
      )}

      {/* ملخص الصافي */}
      {(grossTotal > 0 || returnsTotal > 0) && (
        <Card className="border-2 border-green-200 bg-gradient-to-l from-green-50 to-emerald-50 shadow-md">
          <CardContent className="p-5">
            <h3 className="font-bold text-green-900 mb-4 text-lg">الملخص المحاسبي لليوم</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between items-center pb-2 border-b border-green-200">
                <span className="text-slate-600">إجمالي المبيعات</span>
                <span className="font-bold text-emerald-700">{money(grossTotal)}</span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-green-200">
                <span className="text-slate-600">إجمالي المرتجعات</span>
                <span className="font-bold text-rose-600">- {money(returnsTotal)}</span>
              </div>
              <div className="flex justify-between items-center pt-1">
                <span className="font-bold text-slate-900 text-base">صافي المبيعات</span>
                <span className={`text-2xl font-extrabold ${netTotal >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                  {money(netTotal)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default SalesDaily;
