import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp, DollarSign, Users, Truck, Wallet, Package,
  AlertTriangle, RefreshCw, Receipt, ArrowUpRight, ArrowDownRight,
  Calendar, Award, AlertCircle, Briefcase, ShieldAlert, Banknote, Clock,
  TrendingDown, ShoppingCart,
} from 'lucide-react';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  AreaChart, Area,
} from 'recharts';
import api from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { toast } from '../hooks/use-toast';

const formatNum = (n) => new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(n ?? 0);
const formatMoney = (n) => `${formatNum(n)} ر.ي`;

const PAYMENT_LABELS = {
  cash: 'نقداً', jaib: 'جيب', fluusak: 'فلوسك', hasib: 'حاسب',
  banki: 'بنكي', bank_transfer: 'تحويل', credit: 'آجل',
};
const PIE_COLORS = ['#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#06b6d4', '#ef4444'];

export default function ManagerDashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailView, setDetailView] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    const load = () => {
      setError('');
      api.get('/dashboard/manager')
        .then(r => alive && setData(r.data))
        .catch(e => {
          if (!alive) return;
          const status = e?.response?.status;
          if (status === 403) {
            setError('حسابك لا يملك صلاحية لوحة المدير.');
            toast({ title: 'ليس لديك صلاحية', description: 'لوحة المدير متاحة للمدير فقط', variant: 'destructive' });
          } else if (status === 401) {
            setError('انتهت جلسة الدخول. سجّل الدخول من جديد.');
          } else {
            setError('تعذر تحميل بيانات لوحة المدير. تحقق من اتصال الخادم ثم أعد المحاولة.');
          }
        })
        .finally(() => alive && setLoading(false));
    };
    load();
    const id = setInterval(load, 60000); // refresh every minute
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (loading && !data) {
    return (
      <div className="p-8 flex items-center justify-center h-[60vh]">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 text-amber-500 animate-spin mx-auto mb-3" />
          <p className="text-slate-500">جاري تحميل لوحة المدير...</p>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="p-8 text-center" dir="rtl">
        <ShieldAlert className="w-16 h-16 text-rose-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-rose-700">تعذر تحميل لوحة المدير</h2>
        <p className="text-slate-500 mt-2 mb-5">{error || 'لم تصل بيانات اللوحة بعد.'}</p>
        <Button onClick={() => window.location.reload()} className="bg-amber-500 hover:bg-amber-600 text-white">
          <RefreshCw className="w-4 h-4 ml-2" /> إعادة المحاولة
        </Button>
      </div>
    );
  }

  const hasAlerts = data.alerts.over_credit_limit.length + data.alerts.suppliers_overdue.length +
    data.alerts.low_stock.length + data.alerts.out_of_stock.length + data.alerts.expiring_soon.length > 0;

  return (
    <div className="p-6 lg:p-8 space-y-6" dir="rtl" data-testid="manager-dashboard">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
            <Briefcase className="text-amber-500" /> لوحة المدير المالية
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            مرحباً <span className="font-semibold">{user?.full_name}</span> — آخر تحديث:{' '}
            <span className="font-mono">{new Date(data.as_of).toLocaleString('ar-EG')}</span>
          </p>
        </div>
        <Badge className="bg-amber-100 text-amber-800 border-amber-300 px-4 py-2 text-sm">
          🔐 صلاحيات المدير فقط
        </Badge>
      </div>

      {/* ALERTS BAR */}
      {hasAlerts && (
        <Card className="border-rose-200 bg-gradient-to-l from-rose-50 to-amber-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-5 h-5 text-rose-600" />
              <h3 className="font-bold text-rose-800">تنبيهات ذكية</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
              <AlertChip count={data.alerts.over_credit_limit.length} label="تجاوز حد ائتمان" icon={AlertCircle} color="rose" linkTo="/dashboard/customers" />
              <AlertChip count={data.alerts.suppliers_overdue.length} label="مستحقات تجار" icon={Truck} color="orange" linkTo="/dashboard/purchases" />
              <AlertChip count={data.alerts.low_stock.length} label="مخزون منخفض" icon={Package} color="amber" linkTo="/dashboard/products" />
              <AlertChip count={data.alerts.out_of_stock.length} label="نفد المخزون" icon={Package} color="red" linkTo="/dashboard/products" />
              <AlertChip count={data.alerts.expiring_soon.length} label="قارب انتهاء" icon={Clock} color="purple" linkTo="/dashboard/products" />
            </div>
          </CardContent>
        </Card>
      )}

      {/* COMPACT FINANCIAL SUMMARY */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryLauncher
          title="الأرباح"
          subtitle="يومي وشهري — قبل وبعد المصروفات"
          icon={Award}
          gradient="from-amber-500 to-orange-600"
          onClick={() => setDetailView('profits')}
          value={formatMoney(data.profits.today)}
          valueLabel="ربح اليوم"
        />
        <SummaryLauncher
          title="المبيعات"
          subtitle="صافي المبيعات وطرق الدفع"
          icon={Receipt}
          gradient="from-emerald-500 to-teal-600"
          onClick={() => setDetailView('sales')}
          value={formatMoney(data.sales.net_today)}
          valueLabel="صافي مبيعات اليوم"
        />
        <SummaryLauncher
          title="المشتريات"
          subtitle="إجمالي مشتريات اليوم والشهر"
          icon={ShoppingCart}
          gradient="from-blue-500 to-indigo-600"
          onClick={() => setDetailView('purchases')}
          value={formatMoney(data.purchases.today_total)}
          valueLabel="مشتريات اليوم"
        />
      </section>

      <Dialog open={detailView === 'profits'} onOpenChange={(open) => !open && setDetailView(null)}>
        <DialogContent dir="rtl" className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Award className="text-amber-600" /> تفاصيل الأرباح</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <MetricTile label="ربح اليوم من المنتجات" value={data.profits.today} color="amber" />
            <MetricTile label="ربح اليوم بعد المصروفات" value={data.net_profits?.today} color="emerald" />
            <MetricTile label="ربح الشهر من المنتجات" value={data.profits.month} color="orange" />
            <MetricTile label="ربح الشهر بعد المصروفات" value={data.net_profits?.month} color="teal" />
          </div>
          {data.profit_details && <ProfitDetailsTable details={data.profit_details} />}
        </DialogContent>
      </Dialog>

      <Dialog open={detailView === 'sales'} onOpenChange={(open) => !open && setDetailView(null)}>
        <DialogContent dir="rtl" className="max-w-2xl">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Receipt className="text-emerald-600" /> تفاصيل المبيعات</DialogTitle></DialogHeader>
          <div className="space-y-5">
            <DetailPeriod title="اليوم">
              <MetricTile label="إجمالي المبيعات بعد خصم المرتجعات" value={data.sales.net_today} color="emerald" />
              <MetricTile label="مبيعات نقدية ومحافظ" value={data.sales.today_cash_wallets} color="blue" />
              <MetricTile label="مبيعات آجلة" value={data.sales.today_credit} color="rose" />
            </DetailPeriod>
            <DetailPeriod title="الشهر">
              <MetricTile label="إجمالي المبيعات بعد خصم المرتجعات" value={data.sales.net_month} color="emerald" />
              <MetricTile label="مبيعات نقدية ومحافظ" value={data.sales.month_cash_wallets} color="blue" />
              <MetricTile label="مبيعات آجلة" value={data.sales.month_credit} color="rose" />
            </DetailPeriod>
            <SalesProductsTable title="منتجات مبيعات اليوم" rows={data.sales.product_methods_today} />
            <SalesProductsTable title="منتجات مبيعات الشهر" rows={data.sales.product_methods_month} />
            <div className="grid grid-cols-2 gap-3 text-sm text-slate-600 bg-slate-50 rounded-xl p-3">
              <span>فواتير اليوم: <b>{formatNum(data.sales.invoices_today)}</b></span>
              <span>مرتجعات اليوم: <b>{formatMoney(data.sales.returns_today)}</b></span>
              <span>مرتجعات الشهر: <b>{formatMoney(data.sales.returns_month)}</b></span>
              <span>فواتير الشهر: <b>{formatNum(data.sales.invoices_month || 0)}</b></span>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={detailView === 'purchases'} onOpenChange={(open) => !open && setDetailView(null)}>
        <DialogContent dir="rtl" className="max-w-lg">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><ShoppingCart className="text-blue-600" /> تفاصيل المشتريات</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <MetricTile label="إجمالي مشتريات اليوم" value={data.purchases.today_total} color="blue" />
            <MetricTile label="إجمالي المشتريات الشهرية" value={data.purchases.month_total} color="indigo" />
            <MetricTile label="عدد فواتير اليوم" value={data.purchases.today_count} color="slate" numeric />
            <MetricTile label="عدد فواتير الشهر" value={data.purchases.month_count} color="slate" numeric />
          </div>
        </DialogContent>
      </Dialog>

      {/* الأقسام القديمة محفوظة حسابياً ومخفية لتقليل الازدحام؛ التفاصيل الجديدة في النوافذ أعلاه. */}
      <div className="hidden" aria-hidden="true">
      {/* Cash Box + Returns + Customers + Suppliers Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <Card className="lg:col-span-2 border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 to-teal-50">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-emerald-900 flex items-center gap-2"><Banknote className="w-5 h-5" /> ملخص الصندوق (اليوم)</h3>
              <Badge className="bg-emerald-100 text-emerald-700">حركة اليوم</Badge>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between items-center pb-2 border-b border-emerald-200">
                <span className="text-sm text-slate-600">صافي الصندوق اليوم</span>
                <span className={`text-2xl font-bold ${data.cash_box.current_balance >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}
                      data-testid="cash-current">
                  {formatMoney(data.cash_box.current_balance)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-white/70 rounded p-2">
                  <p className="text-xs text-slate-500">مقبوضات</p>
                  <p className="font-bold text-emerald-600" data-testid="cash-in">{formatMoney(data.cash_box.total_received_today)}</p>
                  <p className="text-xs text-slate-500 mt-1">منها مبيعات نقدية: {formatMoney(data.cash_box.sales_cash)}</p>
                  <p className="text-xs text-slate-500">سندات قبض: {formatMoney(data.cash_box.customer_receipts)}</p>
                </div>
                <div className="bg-white/70 rounded p-2">
                  <p className="text-xs text-slate-500">مدفوعات</p>
                  <p className="font-bold text-rose-600" data-testid="cash-out">{formatMoney(data.cash_box.total_paid_today)}</p>
                  <p className="text-xs text-slate-500 mt-1">مصروفات: {formatMoney(data.cash_box.expenses_paid)}</p>
                  <p className="text-xs text-slate-500">سداد تجار: {formatMoney(data.cash_box.supplier_paid)}</p>
                  <p className="text-xs text-slate-500">مرتجعات: {formatMoney(data.cash_box.cash_returns)}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-2 border-rose-200 bg-gradient-to-br from-rose-50 to-pink-50">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <Users className="w-5 h-5 text-rose-600" />
              <h3 className="font-bold text-rose-900">ديون العملاء</h3>
            </div>
            <p className="text-3xl font-bold text-rose-700 mb-1" data-testid="customers-debt">
              {formatMoney(data.customers.total_debt)}
            </p>
            <p className="text-sm text-slate-600">عدد المدينين: <strong>{data.customers.debtors_count}</strong></p>
            <Link to="/dashboard/customers" className="text-xs text-rose-600 underline mt-2 inline-block">عرض الكل ←</Link>
          </CardContent>
        </Card>

        <Card className="border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-amber-50">
          <CardContent className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <Truck className="w-5 h-5 text-orange-600" />
              <h3 className="font-bold text-orange-900">مستحقات التجار</h3>
            </div>
            <p className="text-3xl font-bold text-orange-700 mb-1" data-testid="suppliers-due">
              {formatMoney(data.suppliers.total_due)}
            </p>
            <p className="text-sm text-slate-600">عدد التجار: <strong>{data.suppliers.due_count}</strong></p>
            <Link to="/dashboard/purchases" className="text-xs text-orange-600 underline mt-2 inline-block">عرض الكل ←</Link>
          </CardContent>
        </Card>
      </div>

      {/* RETURNS + EXPENSES summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-5">
            <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
              <RefreshCw className="w-5 h-5 text-orange-500" /> المرتجعات
            </h3>
            <div className="grid grid-cols-3 gap-3 text-center mb-3">
              <div className="bg-amber-50 p-3 rounded-lg border border-amber-200">
                <p className="text-xs text-amber-700">معلقة</p>
                <p className="text-2xl font-bold text-amber-700" data-testid="ret-pending">{data.returns.pending_count}</p>
              </div>
              <div className="bg-emerald-50 p-3 rounded-lg border border-emerald-200">
                <p className="text-xs text-emerald-700">معتمدة</p>
                <p className="text-2xl font-bold text-emerald-700" data-testid="ret-approved">{data.returns.approved_count}</p>
              </div>
              <div className="bg-rose-50 p-3 rounded-lg border border-rose-200">
                <p className="text-xs text-rose-700">مرفوضة</p>
                <p className="text-2xl font-bold text-rose-700" data-testid="ret-rejected">{data.returns.rejected_count}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="flex justify-between p-2 bg-slate-50 rounded">
                <span className="text-slate-600">إجمالي اليوم</span>
                <strong>{formatMoney(data.returns.today_total)}</strong>
              </div>
              <div className="flex justify-between p-2 bg-slate-50 rounded">
                <span className="text-slate-600">إجمالي الشهر</span>
                <strong>{formatMoney(data.returns.month_total)}</strong>
              </div>
            </div>
            <Link to="/dashboard/returns" className="text-xs text-orange-600 underline mt-3 inline-block">إدارة المرتجعات ←</Link>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
              <Wallet className="w-5 h-5 text-pink-500" /> المصروفات
            </h3>
            <div className="grid grid-cols-3 gap-3 text-center mb-3">
              <div className="bg-pink-50 p-3 rounded-lg">
                <p className="text-xs text-pink-700">اليوم</p>
                <p className="text-xl font-bold text-pink-700" data-testid="exp-today">{formatMoney(data.expenses.today)}</p>
              </div>
              <div className="bg-fuchsia-50 p-3 rounded-lg">
                <p className="text-xs text-fuchsia-700">الشهر</p>
                <p className="text-xl font-bold text-fuchsia-700" data-testid="exp-month">{formatMoney(data.expenses.month)}</p>
              </div>
              <div className="bg-purple-50 p-3 rounded-lg">
                <p className="text-xs text-purple-700">الكلي</p>
                <p className="text-xl font-bold text-purple-700" data-testid="exp-total">{formatMoney(data.expenses.total)}</p>
              </div>
            </div>
            {data.expenses.categories.length > 0 && (
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={data.expenses.categories} dataKey="total" nameKey="category" cx="50%" cy="50%"
                       outerRadius={55} innerRadius={28} paddingAngle={2}>
                    {data.expenses.categories.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => formatMoney(v)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* CHARTS: Sales/Profit/Expenses 30d */}
      <Card>
        <CardContent className="p-5">
          <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-amber-600" /> الأداء المالي - آخر 30 يوم
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data.chart_30d} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gSales" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gExp" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gProfit" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => formatMoney(v)} labelFormatter={(d) => new Date(d).toLocaleDateString('ar-EG')} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Area type="monotone" dataKey="sales" name="إجمالي المبيعات" stroke="#10b981" fill="url(#gSales)" />
              <Area type="monotone" dataKey="returns" name="المرتجعات" stroke="#ef4444" fill="none" strokeDasharray="5 3" />
              <Area type="monotone" dataKey="net_sales" name="صافي المبيعات" stroke="#22c55e" fill="url(#gProfit)" strokeWidth={2} />
              <Area type="monotone" dataKey="expenses" name="المصروفات" stroke="#f43f5e" fill="url(#gExp)" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* ── بطاقات طرق الدفع المفصّلة ── */}
      {data.payment_methods?.length > 0 && (() => {
        const PM_META = [
          { key: 'cash',          label: 'نقداً',       color: '#10b981' },
          { key: 'jaib',          label: 'جيب',         color: '#8b5cf6' },
          { key: 'fluusak',       label: 'فلوسك',       color: '#ec4899' },
          { key: 'hasib',         label: 'حاسب',        color: '#3b82f6' },
          { key: 'banki',         label: 'بنكي',        color: '#06b6d4' },
          { key: 'bank_transfer', label: 'تحويل بنكي',  color: '#6366f1' },
           { key: 'card',          label: 'بطاقة',       color: '#475569' },
          { key: 'credit',        label: 'آجل',         color: '#f43f5e' },
        ];
        const grandTotal    = data.payment_methods.reduce((s, p) => s + Number(p.net_total ?? p.total ?? 0), 0);
        const grandGross    = data.payment_methods.reduce((s, p) => s + Number(p.total ?? 0), 0);
        const grandReturns  = data.payment_methods.reduce((s, p) => s + Number(p.returns_total ?? 0), 0);
        return (
          <section>
            <h2 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2">
              <Wallet className="w-5 h-5 text-purple-600" /> طرق الدفع تفصيلياً — هذا الشهر (صافي المرتجعات)
            </h2>
            {/* ملخص الإجمالي / المرتجعات / الصافي */}
            <div className="grid grid-cols-3 gap-3 mb-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-1">إجمالي المبيعات</p>
                <p className="font-bold text-emerald-700">{formatMoney(grandGross)}</p>
              </div>
              <div className="text-center border-x border-slate-200">
                <p className="text-xs text-slate-500 mb-1">إجمالي المرتجعات</p>
                <p className="font-bold text-rose-600">- {formatMoney(grandReturns)}</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-1">صافي المبيعات</p>
                <p className="font-bold text-green-700">{formatMoney(grandTotal)}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3 mb-2">
              {PM_META.map(({ key, label, color }) => {
                const found = data.payment_methods.find((p) => p.method === key);
                const netTot  = Number(found?.net_total ?? found?.total ?? 0);
                const retTot  = Number(found?.returns_total ?? 0);
                const grossTot = Number(found?.total ?? 0);
                const pct = grandTotal > 0 && found ? Math.round(netTot / grandTotal * 100) : 0;
                return (
                  <Link key={key} to="/dashboard/wallets"
                    className="bg-white rounded-xl border-2 border-slate-100 hover:border-slate-300 p-4 hover:shadow-md transition-all group">
                    <div className="flex items-center justify-between mb-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                           style={{ background: color + '20' }}>
                        <Banknote className="w-4 h-4" style={{ color }} />
                      </div>
                      {pct > 0 && (
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full text-white" style={{ background: color }}>
                          {pct}%
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 font-semibold mb-1">{label}</p>
                    <p className="text-xl font-extrabold text-slate-900">
                      {formatMoney(netTot)}
                    </p>
                    {retTot > 0 && (
                      <p className="text-[10px] text-rose-500 mt-0.5">مرتجعات: - {formatMoney(retTot)}</p>
                    )}
                    <p className="text-xs text-slate-400 mt-0.5">{found?.count || 0} عملية</p>
                  </Link>
                );
              })}
            </div>
          </section>
        );
      })()}

      {/* Payment Methods Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-5">
            <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Banknote className="w-5 h-5 text-blue-600" /> توزيع طرق الدفع (30 يوم)
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={data.payment_methods.map(p => ({ ...p, label: PAYMENT_LABELS[p.method] || p.method }))}
                        margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => formatMoney(v)} />
                <Bar dataKey="total" fill="#3b82f6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-rose-600" /> أكبر 10 عملاء مدينين
            </h3>
            <div className="space-y-2 max-h-[250px] overflow-y-auto">
              {data.customers.top_debtors.length === 0 ? (
                <p className="text-slate-400 text-center py-6">لا توجد ديون حالياً ✓</p>
              ) : data.customers.top_debtors.map((c, i) => (
                <Link key={c.id} to={`/dashboard/customers/${c.id}`}
                  className="flex justify-between items-center bg-rose-50 hover:bg-rose-100 rounded-lg p-2 transition-colors">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-rose-200 text-rose-800 w-7 h-7 rounded-full flex items-center justify-center">{i + 1}</Badge>
                    <div>
                      <p className="font-medium text-sm">{c.name}</p>
                      <p className="text-xs text-slate-500">{c.phone || '—'}</p>
                    </div>
                  </div>
                  <span className="font-bold text-rose-700">{formatMoney(c.balance)}</span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Products */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ProductsList title="أكثر مبيعاً" icon={ShoppingCart} color="emerald" items={data.products.top_selling} field="quantity" />
        <ProductsList title="أعلى ربحاً" icon={Award} color="amber" items={data.products.top_profit} field="profit" money />
        <ProductsList title="أقل مبيعاً" icon={TrendingDown} color="slate" items={data.products.least_selling} field="quantity" />
      </div>

      {/* Suppliers */}
      <Card>
        <CardContent className="p-5">
          <h3 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
            <Truck className="w-5 h-5 text-orange-600" /> أكبر 10 تجار مستحق لهم
          </h3>
          {data.suppliers.top_suppliers.length === 0 ? (
            <p className="text-slate-400 text-center py-4">لا توجد مستحقات حالياً ✓</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {data.suppliers.top_suppliers.map((s, i) => (
                <Link key={s.id} to={`/dashboard/suppliers/${s.id}`}
                  className="flex justify-between items-center bg-orange-50 hover:bg-orange-100 rounded-lg p-3 transition-colors">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-orange-200 text-orange-800 w-7 h-7 rounded-full flex items-center justify-center">{i + 1}</Badge>
                    <div>
                      <p className="font-medium">{s.name}</p>
                      <p className="text-xs text-slate-500">{s.phone || '—'}</p>
                    </div>
                  </div>
                  <span className="font-bold text-orange-700">{formatMoney(s.balance)}</span>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      </div>
    </div>
  );
}

// ============== Sub-components ==============
function SummaryLauncher({ title, subtitle, icon: Icon, gradient, onClick, value, valueLabel }) {
  return (
    <button type="button" onClick={onClick}
      className={`group text-right rounded-2xl bg-gradient-to-br ${gradient} p-5 text-white shadow-md hover:shadow-xl hover:-translate-y-0.5 transition-all focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-2`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-extrabold">{title}</h2>
          <p className="mt-1 text-xs text-white/80">{subtitle}</p>
        </div>
        <span className="rounded-xl bg-white/20 p-2"><Icon className="h-6 w-6" /></span>
      </div>
      <div className="mt-6 flex items-end justify-between">
        <div><p className="text-xs text-white/75">{valueLabel}</p><strong className="text-2xl">{value}</strong></div>
        <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-bold">عرض التفاصيل ←</span>
      </div>
    </button>
  );
}

function MetricTile({ label, value, color = 'slate', numeric = false }) {
  const colors = {
    amber: 'bg-amber-50 border-amber-200 text-amber-800',
    orange: 'bg-orange-50 border-orange-200 text-orange-800',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    teal: 'bg-teal-50 border-teal-200 text-teal-800',
    blue: 'bg-blue-50 border-blue-200 text-blue-800',
    indigo: 'bg-indigo-50 border-indigo-200 text-indigo-800',
    rose: 'bg-rose-50 border-rose-200 text-rose-800',
    slate: 'bg-slate-50 border-slate-200 text-slate-800',
  };
  return <div className={`rounded-xl border p-4 ${colors[color] || colors.slate}`}><p className="text-xs opacity-75">{label}</p><strong className="mt-1 block text-xl">{numeric ? formatNum(value) : formatMoney(value)}</strong></div>;
}

function DetailPeriod({ title, children }) {
  return <div><h3 className="mb-2 font-bold text-slate-700">{title}</h3><div className="grid grid-cols-1 sm:grid-cols-3 gap-2">{children}</div></div>;
}

function SalesProductsTable({ title, rows = [] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200">
      <div className="bg-slate-50 px-3 py-2 font-bold text-slate-700">{title}</div>
      {rows.length === 0 ? <p className="p-4 text-center text-sm text-slate-400">لا توجد مبيعات</p> : (
        <div className="max-h-64 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white text-xs text-slate-500"><tr><th className="p-2 text-right">المنتج</th><th className="p-2 text-right">وسيلة الدفع</th><th className="p-2 text-right">الكمية</th><th className="p-2 text-right">الإجمالي</th></tr></thead>
            <tbody>{rows.map((row, index) => <tr key={`${row.product_id}-${row.payment_method}-${index}`} className="border-t"><td className="p-2 font-medium">{row.product_name}</td><td className="p-2"><Badge className={row.payment_method === 'credit' ? 'bg-rose-100 text-rose-700' : row.payment_method === 'cash' ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'}>{PAYMENT_LABELS[row.payment_method] || row.payment_method}</Badge></td><td className="p-2">{formatNum(row.quantity)}</td><td className="p-2 font-bold">{formatMoney(row.total)}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ProfitDetailsTable({ details }) {
  return (
    <div className="mt-5 overflow-x-auto rounded-xl border border-amber-100">
      <h3 className="bg-amber-50 p-3 font-bold text-amber-900">التفصيل المحاسبي</h3>
      <table className="w-full min-w-[650px] text-sm">
        <thead className="bg-slate-50 text-slate-500"><tr><th className="p-2 text-right">الفترة</th><th className="p-2 text-right">المبيعات</th><th className="p-2 text-right">التكلفة</th><th className="p-2 text-right">المرتجعات</th><th className="p-2 text-right">الربح</th></tr></thead>
        <tbody>{[['اليوم', 'today'], ['الأسبوع', 'week'], ['الشهر', 'month'], ['السنة', 'year']].map(([label, key]) => { const p = details[key] || {}; return <tr key={key} className="border-t"><td className="p-2 font-bold">{label}</td><td className="p-2 text-emerald-700">{formatMoney(p.net_sales)}</td><td className="p-2">{formatMoney(p.net_cogs)}</td><td className="p-2 text-rose-600">{formatMoney(p.returns)}</td><td className="p-2 font-bold text-amber-700">{formatMoney(p.profit)}</td></tr>; })}</tbody>
      </table>
      {details.today?.cost_data_complete === false && <p className="bg-orange-50 p-3 text-xs text-orange-800">تنبيه: توجد {details.today.missing_cost_lines} بنود بدون تكلفة شراء صالحة.</p>}
    </div>
  );
}

function KpiCard({ label, value, gradient, icon: Icon, testid }) {
  return (
    <Card className="overflow-hidden border-0 shadow-lg hover:shadow-2xl transition-all">
      <CardContent className="p-0">
        <div className={`bg-gradient-to-br ${gradient} p-5 text-white`}>
          <div className="flex items-start justify-between mb-3">
            <Icon className="h-7 w-7 opacity-90" />
          </div>
          <p className="text-white/80 text-sm mb-1">{label}</p>
          <p className="text-2xl font-bold" data-testid={testid}>{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function AlertChip({ count, label, icon: Icon, color, linkTo }) {
  const colorMap = {
    rose: 'bg-rose-100 text-rose-700 border-rose-300',
    orange: 'bg-orange-100 text-orange-700 border-orange-300',
    amber: 'bg-amber-100 text-amber-700 border-amber-300',
    red: 'bg-red-100 text-red-700 border-red-300',
    purple: 'bg-purple-100 text-purple-700 border-purple-300',
  };
  return (
    <Link to={linkTo || '#'} className={`flex items-center gap-2 ${colorMap[color]} border rounded-lg p-2 hover:scale-105 transition`}>
      <Icon className="w-5 h-5" />
      <div>
        <p className="text-xs">{label}</p>
        <p className="font-bold text-lg">{count}</p>
      </div>
    </Link>
  );
}

function ProductsList({ title, icon: Icon, color, items, field, money }) {
  const colorMap = {
    emerald: 'text-emerald-600 bg-emerald-100',
    amber: 'text-amber-600 bg-amber-100',
    slate: 'text-slate-600 bg-slate-100',
  };
  return (
    <Card>
      <CardContent className="p-5">
        <h3 className={`font-bold mb-3 flex items-center gap-2 ${colorMap[color]?.split(' ')[0]}`}>
          <Icon className="w-5 h-5" /> {title}
        </h3>
        {items.length === 0 ? (
          <p className="text-slate-400 text-center py-4">لا توجد بيانات</p>
        ) : (
          <div className="space-y-2">
            {items.map((p, i) => (
              <div key={p.id} className="flex items-center gap-2 bg-slate-50 rounded-lg p-2">
                <Badge className={`${colorMap[color]} w-7 h-7 rounded-full flex items-center justify-center`}>{i + 1}</Badge>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate" title={p.name}>{p.name}</p>
                  <p className="text-xs text-slate-400 truncate">{p.sku}</p>
                </div>
                <span className="font-bold text-sm">
                  {money ? formatMoney(p[field]) : formatNum(p[field])}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
