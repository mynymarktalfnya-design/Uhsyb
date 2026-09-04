import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ShoppingCart, AlertTriangle, Users, DollarSign,
  TrendingUp, Receipt, Truck, Wallet, CalendarX,
  Banknote, Clock, RefreshCw, Smartphone, Building2,
} from 'lucide-react';
import { Card, CardContent } from '../components/ui/card';
import api from '../lib/api';
import { useAuth } from '../context/AuthContext';

const formatNum = (n) => new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(n ?? 0);
const formatMoney = (n) => `${formatNum(n)} ر.ي`;

const Dashboard = () => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expiry, setExpiry] = useState(null);
  const { user } = useAuth();
  const canViewPurchases = user?.role !== 'cashier';
  const isCashier = user?.role === 'cashier';
  const isSupervisor = user?.role === 'manager';

  useEffect(() => {
    api.get('/dashboard/summary')
      .then((r) => setSummary(r.data))
      .finally(() => setLoading(false));
    if (!isCashier) {
      api.get('/products/expiry-report')
        .then((r) => setExpiry(r.data))
        .catch(() => {});
    }
  }, [user]);

  // ─── بطاقات الإحصاء الرئيسية ────────────────────────────────────────
  // صف 1: إجمالي المبيعات | المرتجعات | صافي المبيعات
  const salesCards = [
    {
      label: 'إجمالي مبيعات اليوم',
      value: formatMoney(summary?.sales_today),
      icon: DollarSign,
      gradient: 'from-emerald-500 to-teal-600',
      testId: 'stat-sales-today',
      sub: `${formatNum(summary?.invoices_today)} فاتورة`,
    },
    {
      label: 'إجمالي المرتجعات',
      value: formatMoney(summary?.returns_today),
      icon: RefreshCw,
      gradient: 'from-rose-500 to-pink-600',
      testId: 'stat-returns-today',
      sub: summary?.returns_today > 0 ? `${formatNum(summary?.returns_today_count)} مرتجع معتمد` : 'لا مرتجعات اليوم',
    },
    {
      label: 'صافي مبيعات اليوم',
      value: formatMoney(summary?.net_sales_today),
      icon: TrendingUp,
      gradient: 'from-green-600 to-emerald-700',
      testId: 'stat-net-sales-today',
      sub: 'الإجمالي − المرتجعات',
    },
  ];

  // صف 2: تفصيل طرق الدفع
  const methodCards = [
    {
      label: 'نقدي اليوم',
      value: formatMoney(summary?.sales_today_cash),
      icon: Banknote,
      gradient: 'from-blue-500 to-indigo-600',
      testId: 'stat-sales-today-cash',
      sub: null,
    },
    {
      label: 'آجل اليوم',
      value: formatMoney(summary?.sales_today_credit),
      icon: Clock,
      gradient: 'from-amber-500 to-orange-600',
      testId: 'stat-sales-today-credit',
      sub: null,
    },
    {
      label: 'محافظ إلكترونية',
      value: formatMoney(summary?.sales_today_wallets),
      icon: Smartphone,
      gradient: 'from-violet-500 to-purple-600',
      testId: 'stat-sales-today-wallets',
      sub: 'جيب • فلوسك • حاسب',
    },
    {
      label: 'تحويل بنكي',
      value: formatMoney(summary?.sales_today_banks),
      icon: Building2,
      gradient: 'from-indigo-500 to-indigo-700',
      testId: 'stat-sales-today-banks',
      sub: 'بنكي • تحويل',
    },
    {
      label: 'صافي مبيعات الشهر',
      value: formatMoney(summary?.net_sales_month),
      icon: TrendingUp,
      gradient: 'from-teal-500 to-teal-700',
      testId: 'stat-net-sales-month',
      sub: summary?.returns_month > 0 ? `مرتجعات الشهر: ${formatMoney(summary?.returns_month)}` : null,
    },
    {
      label: 'فواتير اليوم',
      value: formatNum(summary?.invoices_today),
      icon: Receipt,
      gradient: 'from-purple-500 to-purple-600',
      testId: 'stat-invoices-today',
      sub: null,
    },
  ];

  // بطاقات الوحدات
  const cards = [
    { title: 'نقطة البيع (POS)', desc: 'بدء فاتورة جديدة بسرعة فائقة', icon: ShoppingCart, link: '/dashboard/pos', color: 'amber' },
    ...(!isSupervisor ? [
      { title: 'مخزون منخفض', desc: `${formatNum(summary?.low_stock_count)} منتج يحتاج تجديد`, icon: AlertTriangle, link: '/dashboard/products?lowStock=1', color: 'red' },
    ] : []),
    { title: 'العملاء', desc: `${formatNum(summary?.customers_count)} عميل مسجّل`, icon: Users, link: '/dashboard/customers', color: 'emerald' },
    { title: 'المصروفات', desc: `${formatMoney(summary?.expenses_month)} هذا الشهر`, icon: Wallet, link: '/dashboard/expenses', color: 'pink' },
  ];
  if (canViewPurchases) {
    cards.push({ title: 'الموردون', desc: `${formatNum(summary?.suppliers_count)} مورد مسجّل`, icon: Truck, link: '/dashboard/purchases', color: 'purple' });
  }

  const colorMap = {
    amber:   'from-amber-50 to-amber-100 border-amber-200 text-amber-700',
    red:     'from-red-50 to-red-100 border-red-200 text-red-700',
    emerald: 'from-emerald-50 to-emerald-100 border-emerald-200 text-emerald-700',
    purple:  'from-purple-50 to-purple-100 border-purple-200 text-purple-700',
    pink:    'from-pink-50 to-pink-100 border-pink-200 text-pink-700',
  };

  return (
    <div className="p-6 lg:p-8" dir="rtl" data-testid="dashboard-page">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-1">لوحة التحكم</h1>
        <p className="text-slate-500">نظرة شاملة على أداء المبيعات اليوم</p>
      </div>

      {/* ─── المعادلة المحاسبية — تظهر دائماً ─── */}
      {!loading && (
        <div className="mb-5 bg-gradient-to-l from-slate-800 to-slate-900 text-white rounded-xl px-5 py-3 shadow-lg flex flex-wrap items-center gap-3 text-sm font-medium">
          <span className="text-slate-400 text-xs ml-1">صافي اليوم:</span>
          <span className="text-emerald-400">{formatMoney(summary?.sales_today)} إجمالي</span>
          <span className="text-slate-500">−</span>
          <span className="text-rose-400">{formatMoney(summary?.returns_today)} مرتجعات</span>
          <span className="text-slate-500">=</span>
          <span className="text-green-400 font-bold text-base">{formatMoney(summary?.net_sales_today)} صافي</span>
        </div>
      )}

      {/* ─── صف 1: الإجمالي / المرتجعات / الصافي ─── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
        {salesCards.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.label} className="overflow-hidden border-0 shadow-lg hover:shadow-2xl transition-all">
              <CardContent className="p-0">
                <div className={`bg-gradient-to-br ${s.gradient} p-5 text-white`}>
                  <div className="flex items-start justify-between mb-3">
                    <Icon className="h-7 w-7 opacity-90" />
                  </div>
                  <p className="text-white/80 text-sm mb-1">{s.label}</p>
                  <p className="text-2xl font-bold" data-testid={s.testId}>{loading ? '...' : s.value}</p>
                  {s.sub && <p className="text-white/70 text-xs mt-1">{s.sub}</p>}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* ─── صف 2: تفصيل طرق الدفع ─── */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">
        {methodCards.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.label} className="overflow-hidden border-0 shadow-md hover:shadow-xl transition-all">
              <CardContent className="p-0">
                <div className={`bg-gradient-to-br ${s.gradient} p-4 text-white`}>
                  <Icon className="h-5 w-5 opacity-90 mb-2" />
                  <p className="text-white/80 text-xs mb-1">{s.label}</p>
                  <p className="text-lg font-bold" data-testid={s.testId}>{loading ? '...' : s.value}</p>
                  {s.sub && <p className="text-white/60 text-[10px] mt-0.5">{s.sub}</p>}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* ─── شريط ملخص المرتجعات ─── */}
      {!loading && (summary?.returns_today ?? 0) > 0 && (
        <div className="mb-6">
          <Link to="/dashboard/returns">
            <div className="bg-gradient-to-l from-orange-50 to-rose-50 border-2 border-orange-300 rounded-xl p-4 shadow-md flex items-center gap-4 hover:shadow-lg transition-all">
              <div className="w-12 h-12 rounded-xl bg-orange-500 flex items-center justify-center flex-shrink-0">
                <RefreshCw className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="text-base font-bold text-orange-900">مرتجعات اليوم المعتمدة</h3>
                <div className="flex flex-wrap gap-4 mt-1 text-sm text-orange-700">
                  <span>إجمالي المبيعات: <strong>{formatMoney(summary?.sales_today)}</strong></span>
                  <span>المرتجعات: <strong className="text-rose-600">− {formatMoney(summary?.returns_today)}</strong></span>
                  <span>صافي المبيعات: <strong className="text-green-700">{formatMoney(summary?.net_sales_today)}</strong></span>
                </div>
              </div>
              <span className="text-orange-600 text-sm underline">عرض ←</span>
            </div>
          </Link>
        </div>
      )}

      {/* ─── تنبيهات تواريخ الصلاحية ─── */}
      {canViewPurchases && expiry && (expiry.expired_count > 0 || (expiry.soon || []).some((p) => p.severity === 'critical' || p.severity === 'warning')) && (
        <div className="mb-6" data-testid="expiry-alert-card">
          <div className="bg-gradient-to-br from-rose-50 to-amber-50 border-2 border-rose-300 rounded-xl p-4 shadow-md">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <CalendarX className="w-6 h-6 text-rose-600" />
                <h3 className="text-base font-bold text-rose-900">تنبيهات تواريخ الصلاحية</h3>
              </div>
              <Link to="/dashboard/products" className="text-xs text-rose-700 underline">عرض الكل ←</Link>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              {expiry.expired_count > 0 && (
                <div className="bg-rose-100 border border-rose-300 rounded-lg p-2.5 text-center">
                  <p className="text-[10px] text-rose-700">منتهية</p>
                  <p className="text-2xl font-extrabold text-rose-700" data-testid="kpi-expired">{expiry.expired_count}</p>
                </div>
              )}
              {(() => {
                const critical = (expiry.soon || []).filter((p) => p.severity === 'critical').length;
                const warning  = (expiry.soon || []).filter((p) => p.severity === 'warning').length;
                const notice   = (expiry.soon || []).filter((p) => p.severity === 'notice').length;
                return (
                  <>
                    {critical > 0 && (
                      <div className="bg-rose-50 border border-rose-200 rounded-lg p-2.5 text-center">
                        <p className="text-[10px] text-rose-600">قريبة جداً (7 أيام)</p>
                        <p className="text-2xl font-extrabold text-rose-600" data-testid="kpi-critical">{critical}</p>
                      </div>
                    )}
                    {warning > 0 && (
                      <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-center">
                        <p className="text-[10px] text-amber-700">قريبة (30 يوم)</p>
                        <p className="text-2xl font-extrabold text-amber-700" data-testid="kpi-warning">{warning}</p>
                      </div>
                    )}
                    {notice > 0 && (
                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-center">
                        <p className="text-[10px] text-slate-600">خلال 90 يوم</p>
                        <p className="text-2xl font-extrabold text-slate-700" data-testid="kpi-notice">{notice}</p>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      )}

      {/* ─── تنبيه المخزون المنخفض ─── */}
      {summary?.low_stock_count > 0 && (
        <div className="mb-6">
          <Link to="/dashboard/products?lowStock=1">
            <div className="bg-gradient-to-br from-amber-50 to-orange-50 border-2 border-amber-300 rounded-xl p-4 shadow-md flex items-center gap-4 hover:shadow-lg transition-all">
              <div className="w-12 h-12 rounded-xl bg-amber-500 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="text-base font-bold text-amber-900">تنبيه مخزون منخفض</h3>
                <p className="text-sm text-amber-700">
                  يوجد <strong>{formatNum(summary?.low_stock_count)}</strong> منتج يحتاج إلى تجديد المخزون
                </p>
              </div>
              <span className="text-amber-600 text-sm underline">عرض ←</span>
            </div>
          </Link>
        </div>
      )}

      {/* ─── الوحدات الرئيسية ─── */}
      <h2 className="text-lg font-bold text-slate-900 mb-4">الوحدات الرئيسية</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <Link to={c.link} key={c.title} data-testid={`module-link-${c.color}`}>
              <Card className="border hover:shadow-xl transition-all duration-300 cursor-pointer group">
                <CardContent className="p-5">
                  <div className={`bg-gradient-to-br ${colorMap[c.color]} w-14 h-14 rounded-2xl flex items-center justify-center mb-4 border group-hover:scale-110 transition-transform`}>
                    <Icon className="h-7 w-7" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900 mb-1">{c.title}</h3>
                  <p className="text-sm text-slate-500">{c.desc}</p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* ─── أفضل 5 منتجات + مخطط المبيعات ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="shadow-md">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-900">أكثر 5 منتجات مبيعاً (30 يوم)</h2>
            </div>
            {summary?.top_products?.length ? (
              <div className="space-y-3">
                {summary.top_products.map((p, i) => (
                  <div key={p.product_id} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors" data-testid={`top-product-${i}`}>
                    <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-700 font-bold flex items-center justify-center text-sm">
                      {i + 1}
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-slate-900">{p.name}</p>
                      <p className="text-xs text-slate-500">{formatNum(p.quantity)} وحدة</p>
                    </div>
                    <span className="font-bold text-emerald-600">{formatMoney(p.revenue)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-400 text-center py-8">لا توجد مبيعات بعد</p>
            )}
          </CardContent>
        </Card>

        <Card className="shadow-md">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-4">مبيعات آخر 7 أيام</h2>
            {summary?.daily_sales?.length ? (
              <div className="h-56 flex items-end justify-between gap-2">
                {summary.daily_sales.map((d, i) => {
                  const max = Math.max(...summary.daily_sales.map((x) => x.total)) || 1;
                  const h = (d.total / max) * 100;
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center gap-2">
                      <div className="w-full bg-slate-100 rounded-t-lg relative" style={{ height: '180px' }}>
                        <div
                          className="absolute bottom-0 left-0 right-0 rounded-t-lg bg-gradient-to-t from-amber-500 to-amber-300 transition-all hover:from-amber-600"
                          style={{ height: `${h}%` }}
                          title={formatMoney(d.total)}
                        />
                      </div>
                      <span className="text-xs text-slate-500">{d.date.slice(5)}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-slate-400 text-center py-8">لا توجد بيانات</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
