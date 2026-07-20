import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Search, Plus, Minus, X, ShoppingCart, Banknote,
  CreditCard, Wallet, Building2, Smartphone, ArrowLeftRight, Clock,
  UserPlus, RotateCcw, Calendar, User, Star, Receipt, Trash2,
  CheckCircle2, AlertCircle, PauseCircle, PlayCircle, Tag,
  Package, Hash, ChevronRight, Zap,
} from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import { toast } from '../hooks/use-toast';
import api, { formatApiError } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import PosReturnsDialog from '../components/pos/PosReturnsDialog';
import { STORE } from '../config/store';

const fmt  = (n) => new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(n || 0);
const fmtK = (n) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(Math.round(n));

const PAYMENT_METHODS = [
  { v: 'cash',          l: 'نقداً',   icon: Banknote,       color: 'from-emerald-500 to-green-600',   ring: 'ring-emerald-400',  bg: 'bg-emerald-500' },
  { v: 'jaib',          l: 'جيب',     icon: Smartphone,     color: 'from-violet-500 to-purple-600',   ring: 'ring-violet-400',   bg: 'bg-violet-500' },
  { v: 'fluusak',       l: 'فلوسك',  icon: Wallet,         color: 'from-pink-500 to-rose-500',       ring: 'ring-pink-400',     bg: 'bg-pink-500' },
  { v: 'hasib',         l: 'حاسب',   icon: CreditCard,     color: 'from-sky-500 to-blue-600',        ring: 'ring-sky-400',      bg: 'bg-sky-500' },
  { v: 'banki',         l: 'بنكي',   icon: Building2,      color: 'from-cyan-500 to-teal-600',       ring: 'ring-cyan-400',     bg: 'bg-cyan-500' },
  { v: 'bank_transfer', l: 'تحويل',  icon: ArrowLeftRight, color: 'from-indigo-500 to-blue-600',     ring: 'ring-indigo-400',   bg: 'bg-indigo-500' },
  { v: 'credit',        l: 'آجل',    icon: Clock,          color: 'from-rose-500 to-red-600',        ring: 'ring-rose-400',     bg: 'bg-rose-500' },
];

const QUICK_AMOUNTS = [500, 1000, 2000, 5000, 10000];
const HELD_KEY = 'pos_held_invoices';

function loadHeld() {
  try { return JSON.parse(localStorage.getItem(HELD_KEY) || '[]'); }
  catch { return []; }
}
function saveHeld(list) {
  try { localStorage.setItem(HELD_KEY, JSON.stringify(list)); } catch {}
}

// ── Category tab pill ──────────────────────────────────────────────────────
function CategoryTab({ label, count, active, onClick, color }) {
  return (
    <button
      onClick={onClick}
      className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95 ${
        active
          ? 'bg-amber-500 text-slate-900 shadow-lg shadow-amber-900/30'
          : 'bg-slate-800/80 text-slate-400 hover:text-white hover:bg-slate-700/80 border border-slate-700/60'
      }`}
    >
      <span>{label}</span>
      {count != null && (
        <span className={`text-[9px] px-1 rounded-full font-extrabold ${active ? 'bg-amber-700/50 text-amber-100' : 'bg-slate-700 text-slate-400'}`}>
          {count}
        </span>
      )}
    </button>
  );
}

// ── Product card ───────────────────────────────────────────────────────────
function ProductCard({ p, onAdd }) {
  const oos  = Number(p.current_stock) <= 0;
  const low  = !oos && Number(p.current_stock) <= 3;
  const [bump, setBump] = useState(false);

  const handleClick = () => {
    if (oos) return;
    onAdd(p);
    setBump(true);
    setTimeout(() => setBump(false), 180);
  };

  return (
    <button
      onClick={handleClick}
      data-testid={`pos-product-${p.sku}`}
      disabled={oos}
      className={`relative rounded-2xl p-3 border-2 text-right flex flex-col justify-between transition-all select-none
        ${bump ? 'scale-95' : 'scale-100'}
        ${oos
          ? 'bg-slate-800/30 border-slate-700/30 opacity-50 cursor-not-allowed'
          : 'bg-gradient-to-br from-slate-800 to-slate-800/60 border-slate-700/40 hover:border-amber-500/60 hover:from-slate-700 active:scale-95 shadow-sm hover:shadow-amber-900/20 hover:shadow-md cursor-pointer'
        }`}
      style={{ minHeight: 96 }}
    >
      {/* Stock badges */}
      {oos && (
        <span className="absolute top-2 left-2 text-[9px] bg-rose-600 text-white px-1.5 py-0.5 rounded-lg font-bold leading-none">نفد</span>
      )}
      {low && (
        <span className="absolute top-2 left-2 text-[9px] bg-amber-600 text-white px-1.5 py-0.5 rounded-lg font-bold leading-none">قليل</span>
      )}
      {p.is_featured && !oos && (
        <span className="absolute top-2 left-2">
          <Star className="w-3 h-3 text-amber-400 fill-amber-400" />
        </span>
      )}

      {/* Name */}
      <p className={`font-bold text-xs leading-snug line-clamp-3 ${oos ? 'text-slate-500' : 'text-slate-100'}`}>
        {p.name}
      </p>

      {/* Price + stock */}
      <div className="mt-2 flex items-end justify-between">
        <span className={`text-base font-extrabold tabular-nums leading-none ${oos ? 'text-slate-600' : 'text-amber-400'}`}>
          {fmt(p.sale_price)}
        </span>
        <div className="flex flex-col items-end gap-0.5">
          <span className="text-[8px] text-slate-500 font-medium">{p.unit || 'قطعة'}</span>
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-lg leading-none ${
            oos ? 'bg-rose-900/50 text-rose-400'
            : low ? 'bg-amber-900/50 text-amber-400'
            : 'bg-slate-700/60 text-slate-400'
          }`}>
            {fmt(p.current_stock)}
          </span>
        </div>
      </div>
    </button>
  );
}

// ── Cart row ───────────────────────────────────────────────────────────────
function CartRow({ item, idx, onUpdateQty, onSetQty, onRemove }) {
  const lineTotal = item.quantity * item.unit_price;

  return (
    <div
      className="group flex items-center gap-2 px-3 py-2.5 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 hover:border-slate-600/60 transition-all"
      data-testid={`cart-item-${idx}`}
    >
      {/* Remove */}
      <button
        onClick={() => onRemove(idx)}
        className="flex-shrink-0 w-6 h-6 rounded-lg flex items-center justify-center text-slate-600 hover:text-rose-400 hover:bg-rose-900/30 transition-all opacity-0 group-hover:opacity-100"
      >
        <X className="w-3 h-3" />
      </button>

      {/* Name */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-white leading-snug line-clamp-2">{item.name}</p>
        <p className="text-[9px] text-slate-500 mt-0.5">{fmt(item.unit_price)} ر.ي / وحدة</p>
      </div>

      {/* Qty controls */}
      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          onClick={() => onUpdateQty(idx, -1)}
          className="w-6 h-6 rounded-lg bg-slate-700 hover:bg-rose-500/80 text-slate-300 hover:text-white flex items-center justify-center transition-all"
        >
          <Minus className="w-2.5 h-2.5" />
        </button>
        <input
          type="number"
          value={item.quantity}
          onChange={(e) => onSetQty(idx, e.target.value)}
          className="w-9 h-6 text-center text-xs font-extrabold bg-slate-700/80 text-amber-300 rounded-lg border border-slate-600/60 focus:outline-none focus:border-amber-500"
          min="0"
        />
        <button
          onClick={() => onUpdateQty(idx, 1)}
          className="w-6 h-6 rounded-lg bg-slate-700 hover:bg-emerald-500/80 text-slate-300 hover:text-white flex items-center justify-center transition-all"
        >
          <Plus className="w-2.5 h-2.5" />
        </button>
      </div>

      {/* Line total */}
      <div className="flex-shrink-0 text-left w-16">
        <p className="text-xs font-extrabold text-amber-400 tabular-nums">{fmt(lineTotal)}</p>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
export default function POS() {
  const { user } = useAuth();

  // Products
  const [allProducts, setAllProducts]         = useState([]);
  const [categories, setCategories]           = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [query, setQuery]                     = useState('');
  const [productsLoading, setProductsLoading] = useState(true);

  // Cart
  const [cart, setCart]                       = useState([]);

  // Barcode
  const [barcode, setBarcode]                 = useState('');
  const barcodeRef                            = useRef(null);
  const searchRef                             = useRef(null);

  // Payment
  const [paymentMethod, setPaymentMethod]     = useState('cash');
  const [cashReceived, setCashReceived]       = useState('');
  const [creditCustomer, setCreditCustomer]   = useState(null);
  const [showCustomerPicker, setShowCustomerPicker] = useState(false);
  const [customers, setCustomers]             = useState([]);
  const [customerSearch, setCustomerSearch]   = useState('');

  // Sale
  const [loading, setLoading]                 = useState(false);
  const [lastInvoice, setLastInvoice]         = useState(null);

  // Held invoices
  const [heldInvoices, setHeldInvoices]       = useState(loadHeld);
  const [showHeldDialog, setShowHeldDialog]   = useState(false);

  // Returns
  const [returnsOpen, setReturnsOpen]         = useState(false);

  // Clock
  const [now, setNow]                         = useState(new Date());

  // ── Boot ──────────────────────────────────────────────────────
  useEffect(() => {
    const tick = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    setProductsLoading(true);
    Promise.all([
      api.get('/pos/products', { params: { limit: 500 } }),
      api.get('/categories'),
    ]).then(([pr, cr]) => {
      setAllProducts(pr.data);
      setCategories(cr.data || []);
    }).catch(() => {}).finally(() => setProductsLoading(false));
    barcodeRef.current?.focus();
  }, []);

  useEffect(() => {
    if (showCustomerPicker) {
      api.get('/customers', { params: { q: customerSearch || undefined } })
        .then((r) => setCustomers(r.data)).catch(() => {});
    }
  }, [showCustomerPicker, customerSearch]);

  // ── Product filtering ─────────────────────────────────────────
  const displayProducts = useMemo(() => {
    let list = allProducts;
    const q = query.trim().toLowerCase();
    if (q) {
      list = list.filter((p) =>
        (p.name || '').toLowerCase().includes(q) ||
        (p.sku  || '').toLowerCase().includes(q) ||
        (p.barcode || '').toLowerCase().includes(q),
      );
    } else if (selectedCategory) {
      list = list.filter((p) => p.category_id === selectedCategory);
    } else {
      // Default: show featured first, then rest
      const featured    = list.filter((p) => p.is_featured);
      const notFeatured = list.filter((p) => !p.is_featured);
      list = [...featured, ...notFeatured];
    }
    return list;
  }, [allProducts, query, selectedCategory]);

  // Category counts
  const categoryCounts = useMemo(() => {
    const m = {};
    allProducts.forEach((p) => {
      if (p.category_id) m[p.category_id] = (m[p.category_id] || 0) + 1;
    });
    return m;
  }, [allProducts]);

  // ── Cart helpers ──────────────────────────────────────────────
  const addToCart = (p) => {
    const stock = Number(p.current_stock ?? 0);
    if (stock <= 0) {
      toast({ title: '⛔ نفد المخزون', description: `"${p.name}" غير متوفر حالياً`, variant: 'destructive' });
      return;
    }
    const existingQty = cart.find((x) => x.product_id === p.id)?.quantity || 0;
    if (existingQty + 1 > stock) {
      toast({ title: '⚠️ تجاوز المخزون', description: `متاح ${fmt(stock)} فقط من "${p.name}"`, variant: 'destructive' });
      return;
    }
    setCart((prev) => {
      const idx = prev.findIndex((x) => x.product_id === p.id);
      if (idx >= 0) {
        const c = [...prev]; c[idx] = { ...c[idx], quantity: c[idx].quantity + 1 }; return c;
      }
      return [...prev, { product_id: p.id, name: p.name, sku: p.sku, unit: p.unit, quantity: 1, unit_price: Number(p.sale_price), stock }];
    });
  };

  const onBarcodeSubmit = async (e) => {
    e.preventDefault();
    if (!barcode.trim()) return;
    try {
      const { data } = await api.get(`/products/by-barcode/${encodeURIComponent(barcode.trim())}`);
      addToCart(data);
      setBarcode('');
      barcodeRef.current?.focus();
    } catch (err) {
      toast({ title: 'باركود غير موجود', description: formatApiError(err), variant: 'destructive' });
      setBarcode('');
    }
  };

  const updateQty = (idx, delta) => {
    setCart((prev) => {
      const c = [...prev];
      const q = c[idx].quantity + delta;
      if (q <= 0) return c.filter((_, i) => i !== idx);
      c[idx] = { ...c[idx], quantity: q };
      return c;
    });
  };

  const setQtyDirect = (idx, val) => {
    const q = Number(val);
    if (isNaN(q) || q < 0) return;
    if (q === 0) setCart((prev) => prev.filter((_, i) => i !== idx));
    else setCart((prev) => { const c = [...prev]; c[idx] = { ...c[idx], quantity: q }; return c; });
  };

  const removeItem = (idx) => setCart((prev) => prev.filter((_, i) => i !== idx));
  const clearCart  = () => { if (window.confirm('مسح السلة كاملاً؟')) { setCart([]); setCashReceived(''); } };

  // ── Held invoices ─────────────────────────────────────────────
  const holdInvoice = () => {
    if (!cart.length) { toast({ title: 'السلة فارغة', variant: 'destructive' }); return; }
    const held = { id: Date.now(), cart: [...cart], paymentMethod, creditCustomer, savedAt: new Date().toISOString(), total: cart.reduce((s, it) => s + it.quantity * it.unit_price, 0) };
    const updated = [...heldInvoices, held];
    setHeldInvoices(updated); saveHeld(updated);
    setCart([]); setCreditCustomer(null); setPaymentMethod('cash'); setCashReceived('');
    toast({ title: `✅ تم تعليق الفاتورة (${held.cart.length} صنف)` });
  };

  const resumeHeld = (held) => {
    if (cart.length > 0 && !window.confirm('السلة الحالية ستُستبدل. متابعة؟')) return;
    setCart(held.cart); setPaymentMethod(held.paymentMethod || 'cash'); setCreditCustomer(held.creditCustomer || null); setCashReceived('');
    const updated = heldInvoices.filter((h) => h.id !== held.id);
    setHeldInvoices(updated); saveHeld(updated); setShowHeldDialog(false);
    toast({ title: 'تم استئناف الفاتورة' });
  };

  const discardHeld = (id) => {
    if (!window.confirm('حذف هذه الفاتورة المعلقة؟')) return;
    const updated = heldInvoices.filter((h) => h.id !== id);
    setHeldInvoices(updated); saveHeld(updated);
  };

  // ── Totals + change ───────────────────────────────────────────
  const total      = cart.reduce((s, it) => s + it.quantity * it.unit_price, 0);
  const received   = parseFloat(cashReceived) || 0;
  const change     = received > 0 ? received - total : 0;

  // ── Payment ───────────────────────────────────────────────────
  const onPaymentSelect = (method) => {
    setPaymentMethod(method);
    setCashReceived('');
    if (method === 'credit') {
      if (!cart.length) { toast({ title: 'أضف منتجاً أولاً', variant: 'destructive' }); return; }
      setShowCustomerPicker(true);
    } else {
      setCreditCustomer(null);
    }
  };

  const selectCustomer = (c) => { setCreditCustomer(c); setShowCustomerPicker(false); };

  // ── Complete sale ─────────────────────────────────────────────
  const completeSale = async () => {
    if (!cart.length) { toast({ title: 'السلة فارغة', variant: 'destructive' }); return; }
    if (paymentMethod === 'credit' && !creditCustomer) { toast({ title: 'اختر عميلاً للبيع الآجل', variant: 'destructive' }); return; }
    setLoading(true);
    try {
      const payload = {
        customer_id: paymentMethod === 'credit' ? creditCustomer.id : null,
        items: cart.map((c) => ({ product_id: c.product_id, quantity: c.quantity, unit_price: c.unit_price })),
        payment_method: paymentMethod,
      };
      const { data } = await api.post('/sales', payload);
      setLastInvoice(data);
      toast({ title: '✅ تم إتمام البيع', description: `فاتورة ${data.invoice_no} — ${fmt(data.total)} ر.ي` });
      setCart([]); setCreditCustomer(null); setPaymentMethod('cash'); setCashReceived('');
      // Refresh stock
      api.get('/pos/products', { params: { limit: 500 } }).then((r) => setAllProducts(r.data)).catch(() => {});
      barcodeRef.current?.focus();
    } catch (e) {
      toast({ title: 'فشل البيع', description: formatApiError(e), variant: 'destructive' });
    } finally { setLoading(false); }
  };

  const activePayment = PAYMENT_METHODS.find((p) => p.v === paymentMethod);
  const canComplete   = cart.length > 0 && !(paymentMethod === 'credit' && !creditCustomer);

  // ══════════════════════════════════════════════════════════════
  return (
    <div
      className="flex flex-col bg-slate-950"
      style={{ height: 'calc(100vh - 60px)' }}
      dir="rtl"
      data-testid="pos-page"
    >

      {/* ══════════ TOP BAR ══════════════════════════════════════ */}
      <div className="flex-shrink-0 h-14 px-3 flex items-center gap-2 bg-gradient-to-l from-slate-900 to-slate-950 border-b border-slate-800">

        {/* Logo + store */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-900/40">
            <ShoppingCart className="w-4.5 h-4.5 text-slate-900 w-5 h-5" />
          </div>
          <div className="hidden sm:block leading-none">
            <p className="text-[11px] font-extrabold text-white tracking-wide">{STORE.name}</p>
            <p className="text-[9px] text-slate-500 flex items-center gap-1 mt-0.5">
              <Calendar className="w-2.5 h-2.5" />
              {now.toLocaleString('ar-EG', { dateStyle: 'short', timeStyle: 'short' })}
            </p>
          </div>
        </div>

        {/* Last invoice badge */}
        {lastInvoice && (
          <div className="hidden md:flex items-center gap-1.5 bg-emerald-500/15 border border-emerald-500/30 rounded-lg px-2 py-1 text-[10px] text-emerald-300 flex-shrink-0">
            <CheckCircle2 className="w-3 h-3" />
            <span className="font-mono font-bold">{lastInvoice.invoice_no}</span>
          </div>
        )}

        {/* Barcode field */}
        <form onSubmit={onBarcodeSubmit} className="flex-1 flex gap-1.5 max-w-xs mx-auto">
          <div className="relative flex-1">
            <Hash className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
            <Input
              ref={barcodeRef}
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              placeholder="امسح الباركود..."
              className="h-9 pr-8 text-sm bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 focus:border-amber-500/70 rounded-xl"
              autoComplete="off"
              data-testid="pos-barcode-input"
            />
          </div>
          <Button type="submit" className="h-9 bg-amber-500 hover:bg-amber-400 text-slate-900 px-3 flex-shrink-0 font-bold text-xs shadow-md shadow-amber-900/30 rounded-xl">
            إضافة
          </Button>
        </form>

        {/* Action buttons */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button
            onClick={holdInvoice}
            disabled={!cart.length}
            title="تعليق الفاتورة"
            className="h-9 px-3 rounded-xl text-xs font-bold bg-slate-800 hover:bg-amber-500/20 hover:text-amber-300 text-slate-400 border border-slate-700 transition-all disabled:opacity-30 flex items-center gap-1.5"
          >
            <PauseCircle className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">تعليق</span>
          </button>

          <button
            onClick={() => setShowHeldDialog(true)}
            title="الفواتير المعلقة"
            className="relative h-9 px-3 rounded-xl text-xs font-bold bg-slate-800 hover:bg-yellow-500/20 hover:text-yellow-300 text-slate-400 border border-slate-700 transition-all flex items-center gap-1.5"
          >
            <PlayCircle className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">معلقة</span>
            {heldInvoices.length > 0 && (
              <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-yellow-400 text-slate-900 rounded-full text-[9px] font-extrabold flex items-center justify-center">
                {heldInvoices.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setReturnsOpen(true)}
            data-testid="pos-open-returns-btn"
            title="مرتجع / استبدال"
            className="h-9 px-3 rounded-xl text-xs font-bold bg-slate-800 hover:bg-rose-500/20 hover:text-rose-300 text-slate-400 border border-slate-700 transition-all flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">مرتجع</span>
          </button>

          {/* User pill */}
          <div className="hidden lg:flex items-center gap-2 bg-slate-800/80 rounded-xl px-3 py-1.5 border border-slate-700/60">
            <div className="w-7 h-7 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center flex-shrink-0">
              <User className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <div className="text-[10px] leading-none">
              <p className="font-bold text-white truncate max-w-[80px]">{user?.full_name?.split(' ')[0] || user?.username}</p>
              <p className="text-slate-500 mt-0.5">
                {user?.role === 'cashier' ? 'كاشير' : user?.role === 'manager' ? 'مشرف' : 'مدير'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ══════════ MAIN AREA ════════════════════════════════════ */}
      <div className="flex-1 flex gap-2 p-2 min-h-0 overflow-hidden">

        {/* ──── LEFT: Products panel (55%) ──────────────────── */}
        <div className="flex-[55] min-w-0 flex flex-col gap-2">

          {/* Search */}
          <div className="relative flex-shrink-0">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
            <Input
              ref={searchRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setSelectedCategory(null); }}
              placeholder="بحث بالاسم أو الباركود أو SKU..."
              className="pr-10 h-10 bg-slate-900 border-slate-700/80 text-white placeholder:text-slate-500 focus:border-amber-500/60 rounded-xl text-sm"
              data-testid="pos-search-input"
            />
            {query && (
              <button onClick={() => setQuery('')} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Category tabs */}
          {!query && categories.length > 0 && (
            <div className="flex gap-1.5 overflow-x-auto flex-shrink-0 pb-0.5" style={{ scrollbarWidth: 'none' }}>
              <CategoryTab
                label="الكل"
                count={allProducts.length}
                active={!selectedCategory}
                onClick={() => setSelectedCategory(null)}
              />
              {categories.map((cat) => (
                <CategoryTab
                  key={cat.id}
                  label={cat.name}
                  count={categoryCounts[cat.id] || 0}
                  active={selectedCategory === cat.id}
                  onClick={() => setSelectedCategory(selectedCategory === cat.id ? null : cat.id)}
                />
              ))}
            </div>
          )}

          {/* Count row */}
          <div className="flex items-center justify-between flex-shrink-0 px-0.5">
            <div className="flex items-center gap-1.5">
              <Package className="w-3 h-3 text-slate-600" />
              <span className="text-[10px] text-slate-500 font-semibold">
                {query ? `نتائج البحث` : selectedCategory ? (categories.find(c => c.id === selectedCategory)?.name || 'المنتجات') : 'المنتجات المميزة'}
                <span className="text-slate-600 mr-1">({displayProducts.length})</span>
              </span>
            </div>
            {productsLoading && (
              <span className="flex items-center gap-1 text-[10px] text-amber-400">
                <span className="w-2.5 h-2.5 border-2 border-amber-400/40 border-t-amber-400 rounded-full animate-spin" />
                تحميل
              </span>
            )}
          </div>

          {/* Product grid */}
          <div
            className="grid gap-2 overflow-y-auto flex-1"
            style={{ minHeight: 0, gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))' }}
          >
            {displayProducts.map((p) => (
              <ProductCard key={p.id} p={p} onAdd={addToCart} />
            ))}

            {!productsLoading && displayProducts.length === 0 && (
              <div className="col-span-full flex flex-col items-center justify-center py-16 text-slate-700">
                {query ? (
                  <>
                    <AlertCircle className="w-10 h-10 mb-3 opacity-30" />
                    <p className="text-sm text-slate-500">لا توجد نتائج لـ "{query}"</p>
                  </>
                ) : (
                  <>
                    <Package className="w-10 h-10 mb-3 opacity-20" />
                    <p className="text-sm text-slate-500">لا توجد منتجات</p>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ──── RIGHT: Invoice + Payment panel (45%) ─────────── */}
        <div className="flex-[45] min-w-[280px] max-w-[420px] flex flex-col bg-slate-900 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden">

          {/* Invoice header */}
          <div className="flex-shrink-0 px-4 py-2.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Receipt className="w-4 h-4 text-amber-400" />
              <h2 className="font-extrabold text-sm text-white tracking-wide">الفاتورة الحالية</h2>
              {cart.length > 0 && (
                <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/25 text-[9px] px-1.5 py-0">
                  {cart.length} صنف
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              {lastInvoice && (
                <span className="text-[9px] text-slate-500 font-mono hidden sm:block">
                  آخر: {lastInvoice.invoice_no}
                </span>
              )}
              {cart.length > 0 && (
                <button onClick={clearCart} className="w-6 h-6 rounded-lg flex items-center justify-center text-slate-600 hover:text-rose-400 hover:bg-rose-900/30 transition-all" title="مسح السلة">
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>

          {/* Cart items — scrollable */}
          <div className="flex-1 overflow-y-auto min-h-0 p-2 space-y-1.5">
            {cart.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-700 py-8">
                <ShoppingCart className="w-14 h-14 mb-3 opacity-10" />
                <p className="text-sm font-medium text-slate-600">السلة فارغة</p>
                <p className="text-xs text-slate-700 mt-1">انقر على منتج أو امسح الباركود</p>
              </div>
            ) : cart.map((it, i) => (
              <CartRow
                key={it.product_id}
                item={it}
                idx={i}
                onUpdateQty={updateQty}
                onSetQty={setQtyDirect}
                onRemove={removeItem}
              />
            ))}
          </div>

          {/* ── Bottom: Total + Payment + Checkout ── */}
          <div className="flex-shrink-0 border-t border-slate-800 bg-slate-950 p-3 space-y-2.5">

            {/* TOTAL */}
            <div className="flex items-center justify-between bg-gradient-to-l from-amber-500/10 to-transparent border border-amber-500/15 rounded-xl px-4 py-2.5">
              <span className="text-xs text-slate-400 font-semibold">الإجمالي</span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-2xl font-extrabold text-amber-400 tabular-nums tracking-tight" data-testid="pos-total">
                  {fmt(total)}
                </span>
                <span className="text-xs text-amber-600 font-bold">ر.ي</span>
              </div>
            </div>

            {/* Cash received + change (only for cash) */}
            {paymentMethod === 'cash' && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Banknote className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
                    <input
                      type="number"
                      value={cashReceived}
                      onChange={(e) => setCashReceived(e.target.value)}
                      placeholder="المبلغ المستلم..."
                      className="w-full h-8 pr-8 pl-3 text-sm font-bold bg-slate-800 border border-slate-700 text-emerald-300 rounded-xl focus:outline-none focus:border-emerald-500 placeholder:text-slate-600 placeholder:font-normal"
                    />
                  </div>
                  {change > 0 && (
                    <div className="flex-shrink-0 bg-emerald-500/15 border border-emerald-500/25 rounded-xl px-3 py-1.5 text-center">
                      <p className="text-[9px] text-emerald-500 font-semibold">الباقي</p>
                      <p className="text-sm font-extrabold text-emerald-400 tabular-nums leading-none">{fmt(change)}</p>
                    </div>
                  )}
                </div>
                {/* Quick amounts */}
                <div className="flex gap-1">
                  {QUICK_AMOUNTS.map((amt) => (
                    <button
                      key={amt}
                      onClick={() => setCashReceived(String(amt))}
                      className="flex-1 h-7 rounded-lg text-[10px] font-bold bg-slate-800 hover:bg-emerald-500/20 hover:text-emerald-300 text-slate-400 border border-slate-700 transition-all active:scale-95"
                    >
                      {fmtK(amt)}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Payment methods */}
            <div>
              <p className="text-[9px] text-slate-600 mb-1.5 font-bold tracking-widest uppercase">طريقة الدفع</p>
              <div className="grid grid-cols-4 gap-1 mb-1">
                {PAYMENT_METHODS.slice(0, 4).map((pm) => {
                  const Icon = pm.icon;
                  const active = paymentMethod === pm.v;
                  return (
                    <button
                      key={pm.v}
                      onClick={() => onPaymentSelect(pm.v)}
                      data-testid={`pos-payment-${pm.v}`}
                      className={`py-2 rounded-xl text-[10px] font-extrabold flex flex-col items-center gap-1 transition-all active:scale-95 ${
                        active
                          ? `bg-gradient-to-br ${pm.color} text-white shadow-lg`
                          : 'bg-slate-800 border border-slate-700/60 text-slate-400 hover:text-white hover:border-slate-500'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      {pm.l}
                    </button>
                  );
                })}
              </div>
              <div className="grid grid-cols-3 gap-1">
                {PAYMENT_METHODS.slice(4).map((pm) => {
                  const Icon = pm.icon;
                  const active = paymentMethod === pm.v;
                  return (
                    <button
                      key={pm.v}
                      onClick={() => onPaymentSelect(pm.v)}
                      data-testid={`pos-payment-${pm.v}`}
                      className={`py-2 rounded-xl text-[10px] font-extrabold flex flex-col items-center gap-1 transition-all active:scale-95 ${
                        active
                          ? `bg-gradient-to-br ${pm.color} text-white shadow-lg`
                          : 'bg-slate-800 border border-slate-700/60 text-slate-400 hover:text-white hover:border-slate-500'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      {pm.l}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Credit customer info */}
            {paymentMethod === 'credit' && (
              <div className="bg-rose-950/60 border border-rose-500/30 rounded-xl p-2.5" data-testid="pos-credit-info">
                {creditCustomer ? (
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <p className="text-sm font-extrabold text-rose-200">{creditCustomer.full_name}</p>
                      <button onClick={() => setShowCustomerPicker(true)} className="text-[10px] text-rose-400 hover:text-rose-200 underline">تغيير</button>
                    </div>
                    <div className="space-y-1 text-[10px] text-slate-400">
                      <div className="flex justify-between">
                        <span>رصيد سابق</span>
                        <span className="font-bold text-rose-300">{fmt(creditCustomer.balance)} ر.ي</span>
                      </div>
                      <div className="flex justify-between text-amber-300">
                        <span>+ هذه الفاتورة</span>
                        <span className="font-bold">{fmt(total)} ر.ي</span>
                      </div>
                      <div className="flex justify-between border-t border-rose-800/60 pt-1 font-extrabold text-rose-200">
                        <span>الرصيد الجديد</span>
                        <span>{fmt(Number(creditCustomer.balance) + total)} ر.ي</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowCustomerPicker(true)}
                    className="w-full text-sm text-rose-300 font-bold flex items-center justify-center gap-2 py-1.5 hover:text-rose-200 transition-colors"
                  >
                    <UserPlus className="w-4 h-4" /> اختر عميلاً للبيع الآجل
                  </button>
                )}
              </div>
            )}

            {/* CHECKOUT BUTTON */}
            <button
              onClick={completeSale}
              disabled={loading || !canComplete}
              data-testid="pos-complete-sale-btn"
              className={`w-full h-13 rounded-xl font-extrabold text-sm transition-all shadow-xl disabled:opacity-40 disabled:cursor-not-allowed leading-none py-3 ${
                canComplete
                  ? `bg-gradient-to-l ${activePayment?.color || 'from-emerald-500 to-green-600'} text-white hover:brightness-110 active:scale-[0.99] shadow-emerald-900/30`
                  : 'bg-slate-800 text-slate-600 border border-slate-700'
              }`}
            >
              {loading ? (
                <span className="flex items-center gap-2 justify-center">
                  <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  جارٍ الحفظ...
                </span>
              ) : cart.length === 0 ? (
                <span className="flex items-center gap-2 justify-center opacity-60">
                  <ShoppingCart className="w-4 h-4" /> إتمام البيع
                </span>
              ) : (
                <span className="flex items-center gap-2 justify-center">
                  <Zap className="w-4 h-4" />
                  إتمام البيع — {fmt(total)} ر.ي
                </span>
              )}
            </button>

            {/* Last invoice confirmation */}
            {lastInvoice && (
              <div className="flex items-center justify-center gap-1.5 text-[10px] text-emerald-400" data-testid="pos-last-invoice">
                <CheckCircle2 className="w-3 h-3" />
                <span>تم: <strong className="font-mono">{lastInvoice.invoice_no}</strong></span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ══════════ DIALOGS ════════════════════════════════════ */}

      {/* Returns */}
      <PosReturnsDialog
        open={returnsOpen}
        onClose={() => setReturnsOpen(false)}
        onCompleted={() => {
          api.get('/pos/products', { params: { limit: 500 } }).then((r) => setAllProducts(r.data)).catch(() => {});
        }}
      />

      {/* Held invoices */}
      <Dialog open={showHeldDialog} onOpenChange={setShowHeldDialog}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <PauseCircle className="w-5 h-5 text-yellow-400" />
              الفواتير المعلقة <Badge className="mr-1 bg-yellow-400/15 text-yellow-300 border-yellow-400/30 border">{heldInvoices.length}</Badge>
            </DialogTitle>
          </DialogHeader>
          {heldInvoices.length === 0 ? (
            <div className="text-center py-10 text-slate-400">
              <PauseCircle className="w-12 h-12 mx-auto mb-3 opacity-20" />
              <p className="text-sm">لا توجد فواتير معلقة</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {heldInvoices.map((held) => (
                <div key={held.id} className="bg-slate-50 border-2 border-slate-200 rounded-xl p-3 hover:border-yellow-400 transition-all">
                  <div className="flex justify-between items-start mb-1.5">
                    <div>
                      <p className="font-bold text-slate-900 text-sm">
                        {held.cart.length} صنف
                        {held.creditCustomer ? ` — ${held.creditCustomer.full_name}` : ''}
                      </p>
                      <p className="text-xs text-slate-400">
                        {new Date(held.savedAt).toLocaleString('ar-EG', { dateStyle: 'short', timeStyle: 'short' })}
                      </p>
                    </div>
                    <p className="font-extrabold text-amber-600 text-lg">{fmt(held.total)} ر.ي</p>
                  </div>
                  <p className="text-xs text-slate-500 mb-2 line-clamp-1">{held.cart.map((i) => i.name).join(' · ')}</p>
                  <div className="flex gap-2">
                    <Button onClick={() => resumeHeld(held)} className="flex-1 h-8 bg-yellow-400 hover:bg-yellow-300 text-slate-900 text-xs font-bold">
                      <PlayCircle className="w-3.5 h-3.5 ml-1" /> استئناف
                    </Button>
                    <Button onClick={() => discardHeld(held.id)} variant="outline" className="h-8 border-rose-300 text-rose-500 hover:bg-rose-50 text-xs px-2.5">
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Customer picker */}
      <Dialog open={showCustomerPicker} onOpenChange={setShowCustomerPicker}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserPlus className="w-5 h-5 text-rose-400" /> اختر عميل — البيع الآجل
            </DialogTitle>
          </DialogHeader>
          <div className="relative mb-2">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              autoFocus
              value={customerSearch}
              onChange={(e) => setCustomerSearch(e.target.value)}
              placeholder="بحث بالاسم أو الهاتف..."
              className="pr-10"
              data-testid="pos-customer-search-input"
            />
          </div>
          <div className="max-h-96 overflow-y-auto space-y-1">
            {customers.length === 0 ? (
              <p className="text-center text-slate-400 py-6 text-sm">لا يوجد عملاء</p>
            ) : customers.map((c) => (
              <button
                key={c.id}
                onClick={() => selectCustomer(c)}
                data-testid={`pos-customer-pick-${c.id}`}
                className="w-full text-right p-3 rounded-xl border border-slate-200 hover:bg-rose-50 hover:border-rose-300 transition-all"
              >
                <div className="flex justify-between items-center">
                  <div>
                    <p className="font-semibold text-slate-900 text-sm">{c.full_name}</p>
                    <p className="text-xs text-slate-500">{c.phone || '—'}</p>
                  </div>
                  <div className="text-left">
                    <p className="text-[9px] text-slate-400">رصيد</p>
                    <p className={`font-extrabold text-sm ${Number(c.balance) > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                      {fmt(c.balance)} ر.ي
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
