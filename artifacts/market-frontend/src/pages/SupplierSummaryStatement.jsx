import React, { useCallback, useEffect, useState } from 'react';
import { ArrowRight, CalendarDays, FileText, MapPin, Phone, Printer, Store, Wallet, X } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import api, { formatApiError } from '../lib/api';
import { toast } from '../hooks/use-toast';
import { STORE } from '../config/store';
import './SupplierSummaryStatement.css';

const money = (value) => new Intl.NumberFormat('ar-EG', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}).format(Number(value) || 0);

const isoDate = (value) => {
  if (!value) return '—';
  const raw = String(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
  return raw.slice(0, 10);
};

const displayDate = (value) => {
  const date = isoDate(value);
  return date === '—' ? date : date;
};

const periodText = (period) => {
  const from = period?.from || 'البداية';
  const to = period?.to || 'حتى الآن';
  return `من ${from} إلى ${to}`;
};

const SummaryCard = ({ icon: Icon, label, value, tone }) => (
  <div className={`summary-kpi summary-kpi--${tone}`}>
    <div className="summary-kpi__icon"><Icon size={23} strokeWidth={2.2} /></div>
    <div>
      <div className="summary-kpi__label">{label}</div>
      <div className="summary-kpi__value">{money(value)} <span>ريال</span></div>
    </div>
  </div>
);

const SupplierSummaryStatement = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState({ from: '', to: '' });
  const [loading, setLoading] = useState(true);
  const [selectedMovement, setSelectedMovement] = useState(null);
  const [movementDetail, setMovementDetail] = useState(null);
  const [movementLoading, setMovementLoading] = useState(false);

  const load = useCallback(async () => {
    if (filters.from && filters.to && filters.from > filters.to) {
      toast({ title: 'الفترة غير صحيحة', description: 'يجب أن يكون تاريخ البداية قبل تاريخ النهاية.', variant: 'destructive' });
      return;
    }
    setLoading(true);
    try {
      const params = {};
      if (filters.from) params.date_from = filters.from;
      if (filters.to) params.date_to = filters.to;
      const response = await api.get(`/suppliers/${id}/summary-statement`, { params });
      setData(response.data);
    } catch (error) {
      toast({
        title: 'تعذر تحميل التقرير',
        description: formatApiError(error),
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [filters.from, filters.to, id]);

  useEffect(() => { load(); }, [load]);

  const openMovement = async (movement) => {
    setSelectedMovement(movement);
    setMovementDetail(movement);
    if (!movement.invoice_id) return;
    setMovementLoading(true);
    try {
      const response = await api.get(`/purchases/${movement.invoice_id}`);
      setMovementDetail({ ...movement, purchase: response.data });
    } catch (error) {
      toast({ title: 'تعذر تحميل تفاصيل الفاتورة', description: formatApiError(error), variant: 'destructive' });
    } finally {
      setMovementLoading(false);
    }
  };

  if (loading && !data) {
    return <div className="p-10 text-center text-slate-400" dir="rtl">جاري تحميل ملخص كشف الحساب...</div>;
  }

  if (!data) {
    return <div className="p-10 text-center text-slate-400" dir="rtl">لا توجد بيانات لهذا التاجر.</div>;
  }

  const supplier = data.supplier || {};
  const summary = data.summary || {};

  return (
    <div className="supplier-summary-shell" dir="rtl" data-testid="supplier-summary-page">
      <div className="no-print supplier-summary-toolbar">
        <div className="flex items-center gap-3">
          <Link to={`/dashboard/suppliers/${id}`} className="text-slate-500 hover:text-slate-900" aria-label="العودة إلى حساب التاجر">
            <ArrowRight className="w-6 h-6" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">ملخص كشف حساب تاجر</h1>
            <p className="text-sm text-slate-500">تقرير مستقل — لا يغيّر الكشف التفصيلي</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => window.print()} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="print-supplier-summary-btn">
            <Printer className="w-4 h-4 ml-1" /> طباعة / PDF
          </Button>
        </div>
      </div>

      <div className="no-print supplier-summary-filters">
        <div>
          <label htmlFor="summary-from">من</label>
          <input id="summary-from" type="date" value={filters.from}
            onChange={(event) => setFilters((current) => ({ ...current, from: event.target.value }))} />
        </div>
        <div>
          <label htmlFor="summary-to">إلى</label>
          <input id="summary-to" type="date" value={filters.to}
            onChange={(event) => setFilters((current) => ({ ...current, to: event.target.value }))} />
        </div>
        <Button onClick={load} variant="outline" className="self-end border-slate-300" data-testid="load-supplier-summary-btn">
          <CalendarDays className="w-4 h-4 ml-1" /> عرض الفترة
        </Button>
        <span className="supplier-summary-filter-hint">اترك التاريخين فارغين لعرض كل الفواتير والمدفوعات.</span>
      </div>

      <article className="supplier-summary-report print-only-block" id="supplier-summary-report">
        <header className="supplier-summary-header">
          <div className="supplier-summary-brand">
            <div className="supplier-summary-logo"><Store size={42} strokeWidth={1.8} /></div>
            <div>
              <div className="supplier-summary-brand-name">{STORE.name}</div>
              <div className="supplier-summary-brand-tagline">{STORE.tagline}</div>
            </div>
          </div>
          <div className="supplier-summary-title-block">
            <div className="supplier-summary-title">ملخص كشف حساب تاجر</div>
            <div className="supplier-summary-identity">
              <div><strong>اسم التاجر:</strong><span>{supplier.name || '—'}</span></div>
              <div><strong>العنوان:</strong><span>{supplier.address || STORE.address || '—'}</span></div>
              <div><strong>رقم الجوال:</strong><span>{supplier.phone || STORE.phone || '—'}</span></div>
            </div>
          </div>
        </header>

        <div className="supplier-summary-orange-rule" />

        <section className="supplier-summary-meta">
          <div className="supplier-summary-meta-item">
            <FileText size={26} />
            <div><span>رقم الكشف</span><strong>{data.report_no || '—'}</strong></div>
          </div>
          <div className="supplier-summary-meta-item">
            <CalendarDays size={26} />
            <div><span>تاريخ الإصدار</span><strong>{displayDate(data.issued_at)}</strong></div>
          </div>
          <div className="supplier-summary-meta-period">
            <span>الفترة</span>
            <strong>{periodText(data.period)}</strong>
          </div>
        </section>

        <section className="supplier-summary-table-wrap">
          <table className="supplier-summary-table" data-testid="supplier-summary-table">
            <thead>
              <tr>
                <th>تاريخ الحركة</th>
                <th>نوع الحركة</th>
                <th>رقم الفاتورة</th>
                <th>رقم الدفعة</th>
                <th>المبلغ</th>
                <th>الرصيد المستحق بعد الحركة</th>
              </tr>
            </thead>
            <tbody>
              {data.movements?.length ? data.movements.map((movement, index) => (
                <tr key={`${movement.payment_id || movement.invoice_id || 'movement'}-${index}`}>
                  <td>{displayDate(movement.date)}</td>
                  <td>
                    <span className={`supplier-summary-movement-badge ${movement.movement_type === 'دفعة للتاجر' ? 'is-payment' : 'is-invoice'}`}>
                      {movement.movement_type}
                    </span>
                  </td>
                  <td>
                    {movement.invoice_no ? (
                      <button type="button" className="supplier-summary-link" onClick={() => openMovement(movement)}>
                        {movement.invoice_no}
                      </button>
                    ) : '—'}
                  </td>
                  <td>
                    {movement.payment_no ? (
                      <button type="button" className="supplier-summary-link supplier-summary-payment-link" onClick={() => openMovement(movement)}>
                        {movement.payment_no}
                      </button>
                    ) : '—'}
                  </td>
                  <td className={`supplier-summary-amount ${movement.movement_type === 'دفعة للتاجر' ? 'is-payment' : ''}`}>
                    {money(movement.amount)}
                  </td>
                   <td className={`supplier-summary-balance ${Number(movement.balance_after) < 0 ? 'is-negative' : ''}`}>
                     {money(movement.balance_after)}
                   </td>
                </tr>
              )) : (
                <tr>
                   <td colSpan="6" className="supplier-summary-empty">لا توجد حركات في الفترة المحددة</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        <div className="supplier-summary-payment-note">
          المبالغ المدفوعة للتاجر مستقلة عن قيمة الفاتورة الأصلية ولا تُخصم منها داخل الجدول.
        </div>

        <section className="supplier-summary-totals" aria-label="ملخص الحساب">
          <SummaryCard icon={Wallet} label="إجمالي فواتير الشراء" value={summary.total_invoices} tone="amount" />
          <SummaryCard icon={Wallet} label="إجمالي الدفعات للتاجر" value={summary.total_payments} tone="paid" />
          <SummaryCard icon={FileText} label="المستحق للتاجر" value={summary.balance} tone="balance" />
        </section>

        <section className="supplier-summary-final">
          <div className="supplier-summary-final-title">الملخص النهائي</div>
          <div className="supplier-summary-final-grid">
            <div><span>إجمالي عدد الفواتير</span><strong>{summary.invoice_count || 0}</strong></div>
            <div><span>إجمالي قيمة فواتير الشراء</span><strong>{money(summary.total_invoices)} ريال</strong></div>
            <div><span>إجمالي عدد الدفعات</span><strong>{summary.payment_count || 0}</strong></div>
            <div><span>إجمالي الدفعات للتاجر</span><strong>{money(summary.total_payments)} ريال</strong></div>
            <div><span>المستحق للتاجر</span><strong>{money(summary.balance)} ريال</strong></div>
          </div>
        </section>

        <footer className="supplier-summary-footer">
          <div><Phone size={16} /> {STORE.phone}</div>
          <div><MapPin size={16} /> {STORE.address}</div>
          <div className="supplier-summary-footer-note">هذا التقرير مختصر ولا يستبدل كشف الحساب التفصيلي</div>
        </footer>
      </article>

      {selectedMovement && (
        <MovementDetailsDialog
          movement={movementDetail || selectedMovement}
          loading={movementLoading}
          onClose={() => { setSelectedMovement(null); setMovementDetail(null); }}
        />
      )}
    </div>
  );
};

const MovementDetailsDialog = ({ movement, loading, onClose }) => {
  const purchase = movement.purchase;
  const methodNames = {
    cash: 'نقداً',
    credit: 'آجل',
    bank_transfer: 'تحويل بنكي',
    banki: 'بنكي',
    card: 'بطاقة',
    jaib: 'جيب',
    fluusak: 'فلوسك',
    hasib: 'حاسب',
  };

  return (
    <div className="supplier-summary-modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="supplier-summary-modal" role="dialog" aria-modal="true" aria-label={`تفاصيل ${movement.movement_type}`}>
        <div className="supplier-summary-modal-header">
          <div>
            <span className={`supplier-summary-movement-badge ${movement.movement_type === 'دفعة للتاجر' ? 'is-payment' : 'is-invoice'}`}>
              {movement.movement_type}
            </span>
            <h2>{movement.invoice_no || movement.payment_no || 'تفاصيل الحركة'}</h2>
          </div>
          <button type="button" className="supplier-summary-modal-close" onClick={onClose} aria-label="إغلاق">
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div className="supplier-summary-modal-loading">جاري تحميل التفاصيل...</div>
        ) : (
          <div className="supplier-summary-modal-body">
            <div className="supplier-summary-detail-grid">
              <div><span>تاريخ الحركة</span><strong>{displayDate(movement.date)}</strong></div>
              <div><span>المبلغ</span><strong>{money(movement.amount)} ريال</strong></div>
              <div><span>رقم الفاتورة</span><strong>{movement.invoice_no || '—'}</strong></div>
              <div><span>رقم الدفعة</span><strong>{movement.payment_no || '—'}</strong></div>
              <div><span>طريقة الدفع</span><strong>{methodNames[movement.payment_method] || movement.payment_method || '—'}</strong></div>
              <div><span>المسجل بواسطة</span><strong>{movement.created_by_name || '—'}</strong></div>
               <div><span>الرصيد المستحق بعد الحركة</span><strong>{money(movement.balance_after)} ريال</strong></div>
            </div>
            {movement.notes && <div className="supplier-summary-detail-note"><span>ملاحظات</span><p>{movement.notes}</p></div>}
            {purchase?.items?.length > 0 && (
              <div className="supplier-summary-items">
                <h3>أصناف الفاتورة</h3>
                {purchase.items.map((item, index) => (
                  <div key={item.id || index}>
                    <span>{item.product_name || 'صنف'}</span>
                    <span>{item.quantity} × {money(item.unit_cost)} = {money(item.total)} ريال</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

export default SupplierSummaryStatement;