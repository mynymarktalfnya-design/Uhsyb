import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { FileText, AlertTriangle, Truck, Calendar, Crown, FileDown, RefreshCw, TrendingUp } from 'lucide-react';
import api from '../lib/api';
import { exportDailyReportPDF } from '../lib/pdfExport';

const fmt = (n) => new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(n || 0);
const money = (n) => `${fmt(n)} ر.ي`;

const MONTH_NAMES_AR = [
  'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
  'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
];

const Reports = () => {
  const [byDay, setByDay] = useState([]);
  const [lowStock, setLowStock] = useState([]);
  const [purchasesDaily, setPurchasesDaily] = useState(null);
  const [purchasesMonthly, setPurchasesMonthly] = useState(null);
  const today = new Date();
  const [selectedYear, setSelectedYear] = useState(today.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(today.getMonth() + 1);
  const [monthlyDetail, setMonthlyDetail] = useState(null);
  const [monthlyDetailLoading, setMonthlyDetailLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('sales'); // sales | purchases-daily | purchases-monthly | low-stock

  useEffect(() => {
    api.get('/reports/sales-by-day', { params: { days: 30 } }).then((r) => setByDay(r.data)).catch(() => {});
    api.get('/reports/low-stock').then((r) => setLowStock(r.data)).catch(() => {});
    api.get('/reports/purchases-daily', { params: { days: 30 } }).then((r) => setPurchasesDaily(r.data)).catch(() => {});
    api.get('/reports/purchases-monthly', { params: { months: 12 } }).then((r) => setPurchasesMonthly(r.data)).catch(() => {});
    api.get('/reports/purchases-monthly', {
      params: { year: today.getFullYear(), month: today.getMonth() + 1, months: 12 },
    }).then((r) => setMonthlyDetail(r.data)).catch(() => {});
  }, []);

  const loadMonthlyDetail = async () => {
    setMonthlyDetailLoading(true);
    try {
      const { data } = await api.get('/reports/purchases-monthly', {
        params: { year: selectedYear, month: selectedMonth, months: 12 },
      });
      setMonthlyDetail(data);
    } catch {
      setMonthlyDetail(null);
    } finally {
      setMonthlyDetailLoading(false);
    }
  };

  const totalRevenue  = byDay.reduce((s, x) => s + x.total, 0);
  const totalReturns  = byDay.reduce((s, x) => s + (x.returns || 0), 0);
  const totalNetSales = byDay.reduce((s, x) => s + (x.net_sales ?? x.total), 0);
  const totalInvoices = byDay.reduce((s, x) => s + x.count, 0);

  const tabs = [
    { id: 'sales',             label: 'المبيعات اليومية',      icon: FileText, testid: 'tab-sales' },
    { id: 'purchases-daily',   label: 'المشتريات اليومية',     icon: Truck,    testid: 'tab-purchases-daily' },
    { id: 'purchases-monthly', label: 'المشتريات الشهرية',     icon: Calendar, testid: 'tab-purchases-monthly' },
    { id: 'low-stock',         label: 'المخزون المنخفض',       icon: AlertTriangle, testid: 'tab-low-stock' },
  ];

  return (
    <div className="p-6 lg:p-8" dir="rtl" data-testid="reports-page">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-1">التقارير</h1>
        <p className="text-slate-500">تحليل أداء الميني ماركت</p>
      </div>

      {/* Top KPI Cards (sales summary always visible) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <Card data-testid="kpi-revenue-30d">
          <CardContent className="p-4">
            <h3 className="text-xs text-slate-500 mb-1">إجمالي المبيعات (30 يوم)</h3>
            <p className="text-xl font-bold text-emerald-600">{money(totalRevenue)}</p>
          </CardContent>
        </Card>
        <Card data-testid="kpi-returns-30d" className="border-rose-200">
          <CardContent className="p-4">
            <h3 className="text-xs text-slate-500 mb-1 flex items-center gap-1">
              <RefreshCw className="w-3 h-3 text-rose-500" /> إجمالي المرتجعات (30 يوم)
            </h3>
            <p className="text-xl font-bold text-rose-600">- {money(totalReturns)}</p>
          </CardContent>
        </Card>
        <Card data-testid="kpi-net-sales-30d" className="border-green-200 bg-green-50">
          <CardContent className="p-4">
            <h3 className="text-xs text-slate-500 mb-1 flex items-center gap-1">
              <TrendingUp className="w-3 h-3 text-green-600" /> صافي المبيعات (30 يوم)
            </h3>
            <p className="text-xl font-bold text-green-700">{money(totalNetSales)}</p>
          </CardContent>
        </Card>
        <Card data-testid="kpi-invoices-30d">
          <CardContent className="p-4">
            <h3 className="text-xs text-slate-500 mb-1">فواتير البيع (30 يوم)</h3>
            <p className="text-xl font-bold text-amber-600">{fmt(totalInvoices)}</p>
          </CardContent>
        </Card>
        <Card data-testid="kpi-purchases-30d-total">
          <CardContent className="p-4">
            <h3 className="text-xs text-slate-500 mb-1">مشتريات (30 يوم)</h3>
            <p className="text-xl font-bold text-indigo-600">{money(purchasesDaily?.grand_total)}</p>
          </CardContent>
        </Card>
        <Card data-testid="kpi-purchases-30d-count">
          <CardContent className="p-4">
            <h3 className="text-xs text-slate-500 mb-1">فواتير الشراء (30 يوم)</h3>
            <p className="text-xl font-bold text-purple-600">{fmt(purchasesDaily?.grand_invoices_count)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-6 border-b border-slate-200">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              data-testid={t.testid}
              className={`flex items-center gap-2 px-4 py-2 -mb-px text-sm font-medium border-b-2 transition-all ${
                active
                  ? 'border-amber-500 text-amber-700'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* SALES BY DAY */}
      {activeTab === 'sales' && (
        <Card data-testid="panel-sales">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5" /> مبيعات يومية (30 يوم)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-700">
                  <tr>
                    <th className="px-4 py-2 text-right">التاريخ</th>
                    <th className="px-4 py-2 text-right">فواتير</th>
                    <th className="px-4 py-2 text-right">إجمالي المبيعات</th>
                    <th className="px-4 py-2 text-right text-rose-600">المرتجعات</th>
                    <th className="px-4 py-2 text-right text-green-700">صافي المبيعات</th>
                  </tr>
                </thead>
                <tbody>
                  {byDay.length === 0 && <tr><td colSpan="5" className="text-center py-6 text-slate-400">لا بيانات</td></tr>}
                  {byDay.map((d) => (
                    <tr key={d.date} className="border-t hover:bg-slate-50" data-testid={`sales-row-${d.date}`}>
                      <td className="px-4 py-2">{d.date}</td>
                      <td className="px-4 py-2">{d.count}</td>
                      <td className="px-4 py-2 font-bold text-emerald-600">{money(d.total)}</td>
                      <td className="px-4 py-2 text-rose-600">
                        {(d.returns || 0) > 0 ? `- ${money(d.returns)}` : <span className="text-slate-300">—</span>}
                      </td>
                      <td className="px-4 py-2 font-bold text-green-700">{money(d.net_sales ?? d.total)}</td>
                    </tr>
                  ))}
                </tbody>
                {byDay.length > 0 && (
                  <tfoot className="bg-slate-100 font-bold text-slate-800 border-t-2">
                    <tr>
                      <td className="px-4 py-2">الإجمالي (30 يوم)</td>
                      <td className="px-4 py-2">{fmt(totalInvoices)}</td>
                      <td className="px-4 py-2 text-emerald-700">{money(totalRevenue)}</td>
                      <td className="px-4 py-2 text-rose-600">{totalReturns > 0 ? `- ${money(totalReturns)}` : '—'}</td>
                      <td className="px-4 py-2 text-green-800">{money(totalNetSales)}</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* PURCHASES DAILY */}
      {activeTab === 'purchases-daily' && (
        <div className="space-y-6">
          <div className="flex justify-end">
            <Button
              onClick={() => exportDailyReportPDF({
                title: 'تقرير المشتريات اليومية',
                dateLabel: `آخر ${purchasesDaily?.days || 30} يوم`,
                kpis: [
                  { label: 'إجمالي مشتريات الفترة', value: `${money(purchasesDaily?.grand_total)} ر.ي`, color: 'purple' },
                  { label: 'عدد فواتير الشراء', value: fmt(purchasesDaily?.grand_invoices_count), color: 'blue' },
                  { label: 'عدد الأيام', value: fmt(purchasesDaily?.days || 30), color: 'amber' },
                ],
                columns: ['التاريخ', 'رقم الفاتورة', 'اسم التاجر', 'قيمة الفاتورة (ر.ي)'],
                rows: (purchasesDaily?.invoices || []).map((inv) => [
                  inv.date, inv.ref_no, inv.supplier_name, money(inv.total),
                ]),
                grandRow: ['الإجمالي', '', '', money(purchasesDaily?.grand_total)],
              })}
              disabled={!purchasesDaily?.invoices?.length}
              className="bg-rose-500 hover:bg-rose-600 text-white"
              data-testid="export-purchases-daily-pdf-btn"
            >
              <FileDown className="w-4 h-4 ml-1" /> تصدير PDF
            </Button>
          </div>

          {/* Per-day aggregate */}
          <Card data-testid="panel-purchases-daily-summary">
            <CardContent className="p-6">
              <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                <Truck className="w-5 h-5 text-indigo-600" /> إجمالي مشتريات كل يوم
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-700">
                    <tr>
                      <th className="px-4 py-2 text-right">التاريخ</th>
                      <th className="px-4 py-2 text-right">عدد الفواتير</th>
                      <th className="px-4 py-2 text-right">إجمالي مشتريات اليوم</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(!purchasesDaily?.daily_totals?.length) && (
                      <tr><td colSpan="3" className="text-center py-6 text-slate-400">لا توجد بيانات مشتريات</td></tr>
                    )}
                    {purchasesDaily?.daily_totals?.map((d) => (
                      <tr key={d.date} className="border-t" data-testid={`purchases-daily-row-${d.date}`}>
                        <td className="px-4 py-2 font-medium">{d.date}</td>
                        <td className="px-4 py-2">{d.invoices_count}</td>
                        <td className="px-4 py-2 font-bold text-indigo-600">{money(d.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                  {purchasesDaily?.daily_totals?.length > 0 && (
                    <tfoot className="bg-indigo-50 font-bold">
                      <tr>
                        <td className="px-4 py-2">الإجمالي ({purchasesDaily.days} يوم)</td>
                        <td className="px-4 py-2">{fmt(purchasesDaily.grand_invoices_count)}</td>
                        <td className="px-4 py-2 text-indigo-700" data-testid="purchases-daily-grand-total">{money(purchasesDaily.grand_total)}</td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Detail per invoice */}
          <Card data-testid="panel-purchases-daily-invoices">
            <CardContent className="p-6">
              <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                <Truck className="w-5 h-5 text-indigo-600" /> تفاصيل فواتير الشراء
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-700">
                    <tr>
                      <th className="px-4 py-2 text-right">التاريخ</th>
                      <th className="px-4 py-2 text-right">رقم الفاتورة</th>
                      <th className="px-4 py-2 text-right">اسم التاجر</th>
                      <th className="px-4 py-2 text-right">قيمة الفاتورة</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(!purchasesDaily?.invoices?.length) && (
                      <tr><td colSpan="4" className="text-center py-6 text-slate-400">لا توجد فواتير</td></tr>
                    )}
                    {purchasesDaily?.invoices?.map((inv) => (
                      <tr key={inv.id} className="border-t" data-testid={`purchases-invoice-row-${inv.ref_no}`}>
                        <td className="px-4 py-2">{inv.date}</td>
                        <td className="px-4 py-2 text-slate-500">{inv.ref_no}</td>
                        <td className="px-4 py-2 font-medium">{inv.supplier_name}</td>
                        <td className="px-4 py-2 font-bold text-indigo-600">{money(inv.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* PURCHASES MONTHLY */}
      {activeTab === 'purchases-monthly' && (
        <div className="space-y-6">
          <Card className="border-2 border-purple-200 bg-purple-50/50" data-testid="monthly-purchase-filter">
            <CardContent className="p-5">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-purple-600" /> كشف مشتريات شهر محدد
                  </h2>
                  <p className="text-sm text-slate-500 mt-1">
                    اختر الشهر لعرض جميع الفواتير والأصناف والتجار والأسعار والمدفوعات بالتفصيل.
                  </p>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <label className="text-sm font-medium text-slate-700">
                    الشهر
                    <select
                      value={selectedMonth}
                      onChange={(e) => setSelectedMonth(Number(e.target.value))}
                      className="block mt-1 h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
                      data-testid="purchases-month-select"
                    >
                      {MONTH_NAMES_AR.map((name, index) => (
                        <option key={name} value={index + 1}>{name}</option>
                      ))}
                    </select>
                  </label>
                  <label className="text-sm font-medium text-slate-700">
                    السنة
                    <select
                      value={selectedYear}
                      onChange={(e) => setSelectedYear(Number(e.target.value))}
                      className="block mt-1 h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
                      data-testid="purchases-year-select"
                    >
                      {Array.from({ length: 11 }, (_, index) => today.getFullYear() - index).map((year) => (
                        <option key={year} value={year}>{year}</option>
                      ))}
                    </select>
                  </label>
                  <Button
                    onClick={loadMonthlyDetail}
                    disabled={monthlyDetailLoading}
                    className="bg-purple-600 hover:bg-purple-700 text-white"
                    data-testid="load-purchases-month-btn"
                  >
                    <RefreshCw className={`w-4 h-4 ml-1 ${monthlyDetailLoading ? 'animate-spin' : ''}`} />
                    {monthlyDetailLoading ? 'جارٍ التحميل…' : 'عرض الكشف'}
                  </Button>
                  <Button
                    onClick={() => {
                      const rows = (monthlyDetail?.invoices || []).flatMap((invoice) => (
                        invoice.items?.length
                          ? invoice.items.map((item, index) => [
                              index === 0 ? invoice.date : '',
                              index === 0 ? invoice.ref_no : '',
                              index === 0 ? invoice.supplier_name : '',
                              `${item.product_name} — ${fmt(item.quantity)} ${item.unit || ''}`,
                              money(item.unit_cost),
                              money(item.total),
                              index === 0 ? money(invoice.total) : '',
                              index === 0 ? money(invoice.paid_amount) : '',
                              index === 0 ? money(invoice.remaining) : '',
                            ])
                          : [[invoice.date, invoice.ref_no, invoice.supplier_name, 'لا توجد أصناف', '', '', money(invoice.total), money(invoice.paid_amount), money(invoice.remaining)]]
                      ));
                      exportDailyReportPDF({
                        title: 'كشف مشتريات شهري',
                        dateLabel: `${MONTH_NAMES_AR[(monthlyDetail?.month || selectedMonth) - 1]} ${monthlyDetail?.year || selectedYear}`,
                        kpis: [
                          { label: 'إجمالي المشتريات', value: money(monthlyDetail?.selected?.total), color: 'purple' },
                          { label: 'المدفوع', value: money(monthlyDetail?.selected?.paid_total), color: 'green' },
                          { label: 'المتبقي', value: money(monthlyDetail?.selected?.remaining_total), color: 'rose' },
                          { label: 'الفواتير', value: fmt(monthlyDetail?.selected?.invoices_count), color: 'blue' },
                        ],
                        columns: ['التاريخ', 'رقم الفاتورة', 'التاجر', 'الصنف والكمية', 'سعر الوحدة', 'إجمالي الصنف', 'إجمالي الفاتورة', 'المدفوع', 'المتبقي'],
                        rows,
                        grandRow: ['الإجمالي', '', '', '', '', '', money(monthlyDetail?.selected?.total), money(monthlyDetail?.selected?.paid_total), money(monthlyDetail?.selected?.remaining_total)],
                      });
                    }}
                    disabled={!monthlyDetail?.invoices?.length}
                    className="bg-rose-500 hover:bg-rose-600 text-white"
                    data-testid="export-purchases-monthly-detail-pdf-btn"
                  >
                    <FileDown className="w-4 h-4 ml-1" /> طباعة كشف الشهر
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              ['إجمالي مشتريات الشهر', monthlyDetail?.selected?.total, 'text-purple-700', 'bg-purple-50 border-purple-200'],
              ['المدفوع', monthlyDetail?.selected?.paid_total, 'text-emerald-700', 'bg-emerald-50 border-emerald-200'],
              ['المتبقي', monthlyDetail?.selected?.remaining_total, 'text-rose-700', 'bg-rose-50 border-rose-200'],
              ['عدد الفواتير', monthlyDetail?.selected?.invoices_count, 'text-blue-700', 'bg-blue-50 border-blue-200'],
            ].map(([label, value, color, bg]) => (
              <Card key={label} className={`border-2 ${bg}`}>
                <CardContent className="p-4">
                  <p className="text-xs text-slate-500 mb-1">{label}</p>
                  <p className={`text-xl font-bold ${color}`}>
                    {label === 'عدد الفواتير' ? fmt(value) : money(value)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card data-testid="panel-purchases-monthly-detail">
            <CardContent className="p-6">
              <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-purple-600" />
                تفاصيل مشتريات {MONTH_NAMES_AR[(monthlyDetail?.month || selectedMonth) - 1]} {monthlyDetail?.year || selectedYear}
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-700">
                    <tr>
                      <th className="px-3 py-2 text-right">التاريخ</th>
                      <th className="px-3 py-2 text-right">رقم الفاتورة</th>
                      <th className="px-3 py-2 text-right">التاجر</th>
                      <th className="px-3 py-2 text-right">الصنف</th>
                      <th className="px-3 py-2 text-right">الكمية</th>
                      <th className="px-3 py-2 text-right">سعر الوحدة</th>
                      <th className="px-3 py-2 text-right">إجمالي الصنف</th>
                      <th className="px-3 py-2 text-right">إجمالي الفاتورة</th>
                      <th className="px-3 py-2 text-right">المدفوع</th>
                      <th className="px-3 py-2 text-right">المتبقي</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(!monthlyDetail?.invoices?.length) && (
                      <tr><td colSpan="10" className="text-center py-8 text-slate-400">لا توجد مشتريات في هذا الشهر</td></tr>
                    )}
                    {monthlyDetail?.invoices?.flatMap((invoice) => (
                      (invoice.items?.length ? invoice.items : [{ product_name: 'لا توجد أصناف', quantity: 0, unit: '', unit_cost: 0, total: 0 }]).map((item, index) => (
                        <tr key={`${invoice.id}-${item.id || index}`} className="border-t hover:bg-purple-50/40">
                          <td className="px-3 py-2 whitespace-nowrap">{index === 0 ? invoice.date : ''}</td>
                          <td className="px-3 py-2 text-slate-500">{index === 0 ? invoice.ref_no : ''}</td>
                          <td className="px-3 py-2 font-medium">{index === 0 ? invoice.supplier_name : ''}</td>
                          <td className="px-3 py-2">{item.product_name}</td>
                          <td className="px-3 py-2">{fmt(item.quantity)} {item.unit}</td>
                          <td className="px-3 py-2">{money(item.unit_cost)}</td>
                          <td className="px-3 py-2 font-medium">{money(item.total)}</td>
                          <td className="px-3 py-2 font-bold text-purple-700">{index === 0 ? money(invoice.total) : ''}</td>
                          <td className="px-3 py-2 text-emerald-700">{index === 0 ? money(invoice.paid_amount) : ''}</td>
                          <td className="px-3 py-2 text-rose-700">{index === 0 ? money(invoice.remaining) : ''}</td>
                        </tr>
                      ))
                    ))}
                  </tbody>
                  {monthlyDetail?.selected && (
                    <tfoot className="bg-purple-50 font-bold border-t-2">
                      <tr>
                        <td className="px-3 py-3" colSpan="7">إجمالي مشتريات الشهر</td>
                        <td className="px-3 py-3 text-purple-800">{money(monthlyDetail.selected.total)}</td>
                        <td className="px-3 py-3 text-emerald-700">{money(monthlyDetail.selected.paid_total)}</td>
                        <td className="px-3 py-3 text-rose-700">{money(monthlyDetail.selected.remaining_total)}</td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </CardContent>
          </Card>

          <Card data-testid="panel-purchases-monthly">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-purple-600" /> المشتريات الشهرية (آخر 12 شهر)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-700">
                  <tr>
                    <th className="px-4 py-2 text-right">الشهر</th>
                    <th className="px-4 py-2 text-right">عدد الفواتير</th>
                    <th className="px-4 py-2 text-right">منتجات أُضيفت</th>
                    <th className="px-4 py-2 text-right">
                      <span className="inline-flex items-center gap-1"><Crown className="w-4 h-4 text-amber-500" /> أكثر تاجر</span>
                    </th>
                    <th className="px-4 py-2 text-right">إجمالي مشتريات الشهر</th>
                  </tr>
                </thead>
                <tbody>
                  {(!purchasesMonthly?.months?.length) && (
                    <tr><td colSpan="5" className="text-center py-6 text-slate-400">لا توجد بيانات</td></tr>
                  )}
                  {purchasesMonthly?.months?.map((m) => (
                    <tr key={m.month_label} className="border-t" data-testid={`purchases-monthly-row-${m.month_label}`}>
                      <td className="px-4 py-2 font-medium">{MONTH_NAMES_AR[m.month - 1]} {m.year}</td>
                      <td className="px-4 py-2">{fmt(m.invoices_count)}</td>
                      <td className="px-4 py-2">{fmt(m.products_added)}</td>
                      <td className="px-4 py-2">
                        {m.top_supplier ? (
                          <div>
                            <p className="font-medium text-slate-800">{m.top_supplier.name}</p>
                            <p className="text-xs text-slate-500">{money(m.top_supplier.total)} • {m.top_supplier.count} فاتورة</p>
                          </div>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2 font-bold text-purple-700">{money(m.total)}</td>
                    </tr>
                  ))}
                </tbody>
                {purchasesMonthly?.months?.length > 0 && (
                  <tfoot className="bg-purple-50 font-bold">
                    <tr>
                      <td className="px-4 py-2">الإجمالي العام</td>
                      <td className="px-4 py-2">{fmt(purchasesMonthly.grand_invoices_count)}</td>
                      <td className="px-4 py-2">—</td>
                      <td className="px-4 py-2">—</td>
                      <td className="px-4 py-2 text-purple-800" data-testid="purchases-monthly-grand-total">{money(purchasesMonthly.grand_total)}</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </CardContent>
        </Card>
        </div>
      )}

      {/* LOW STOCK */}
      {activeTab === 'low-stock' && (
        <Card data-testid="panel-low-stock">
          <CardContent className="p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-rose-500" /> المنتجات منخفضة المخزون
            </h2>
            {lowStock.length === 0 ? (
              <p className="text-slate-400 text-center py-6">لا توجد منتجات منخفضة</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-700">
                    <tr>
                      <th className="px-4 py-2 text-right">المنتج</th>
                      <th className="px-4 py-2 text-right">SKU</th>
                      <th className="px-4 py-2 text-right">المخزون الحالي</th>
                      <th className="px-4 py-2 text-right">الحد الأدنى</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lowStock.map((p) => (
                      <tr key={p.id} className="border-t">
                        <td className="px-4 py-2 font-medium">{p.name}</td>
                        <td className="px-4 py-2 text-slate-500">{p.sku}</td>
                        <td className="px-4 py-2 font-bold text-rose-600">{fmt(p.current_stock)} {p.unit}</td>
                        <td className="px-4 py-2">{p.min_stock_level}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default Reports;
