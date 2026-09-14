import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  Search, Plus, Minus, X, ShoppingCart, Banknote,
  CreditCard, Wallet, Building2, Smartphone, ArrowLeftRight, Clock,
  UserPlus, RotateCcw, Trash2, CheckCircle2, PauseCircle, PlayCircle,
  Bell, Wifi, Menu, ScanLine, Package, Droplets, Tag, Milk,
  Sparkles, Coffee, Beef, Apple, ChevronRight, Receipt, User, Star,
  Hash, MoreHorizontal, ShoppingBasket, Boxes,
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

const fmt = (n) => new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 2 }).format(n || 0);

/* ─── Payment methods (same wallets as before, no mixed) ───────────────── */
const PAYMENT_METHODS = [
  { v: 'cash',          l: 'نقد',     icon: Banknote,       grad: 'from-emerald-600 to-green-500',    ring: 'ring-emerald-400',  light: '#22c55e' },
  { v: 'jaib',          l: 'جيب',     icon: Smartphone,     grad: 'from-purple-600 to-violet-500',    ring: 'ring-purple-400',   light: '#a855f7' },
  { v: 'fluusak',       l: 'فلوسك',  icon: Wallet,         grad: 'from-orange-500 to-amber-500',     ring: 'ring-orange-400',   light: '#f97316' },
  { v: 'hasib',         l: 'حاسب',   icon: CreditCard,     grad: 'from-sky-600 to-blue-500',         ring: 'ring-sky-400',      light: '#0ea5e9' },
  { v: 'banki',         l: 'بنكي',   icon: Building2,      grad: 'from-teal-600 to-cyan-500',        ring: 'ring-teal-400',     light: '#14b8a6' },
  { v: 'bank_transfer', l: 'تحويل',  icon: ArrowLeftRight, grad: 'from-indigo-600 to-blue-500',      ring: 'ring-indigo-400',   light: '#6366f1' },
  { v: 'credit',        l: 'آجل',    icon: Clock,          grad: 'from-rose-600 to-red-500',         ring: 'ring-rose-400',     light: '#f43f5e' },
];

/* ─── Category icon helper ─────────────────────────────────────────────── */
const CAT_PALETTES = [
  { icon: Droplets,      bg: 'bg-blue-500',    text: 'text-blue-400',    glow: '#3b82f6' },
  { icon: Coffee,        bg: 'bg-orange-500',  text: 'text-orange-400',  glow: '#f97316' },
  { icon: Milk,          bg: 'bg-sky-400',     text: 'text-sky-300',     glow: '#38bdf8' },
  { icon: Boxes,         bg: 'bg-green-500',   text: 'text-green-400',   glow: '#22c55e' },
  { icon: Sparkles,      bg: 'bg-purple-500',  text: 'text-purple-400',  glow: '#a855f7' },
  { icon: Apple,         bg: 'bg-red-500',     text: 'text-red-400',     glow: '#ef4444' },
  { icon: Beef,          bg: 'bg-amber-500',   text: 'text-amber-400',   glow: '#f59e0b' },
  { icon: Package,       bg: 'bg-slate-500',   text: 'text-slate-300',   glow: '#64748b' },
];

const getCatPalette = (idx) => CAT_PALETTES[idx % CAT_PALETTES.length];

const HELD_KEY = 'pos_held_invoices';
function loadHeld() { try { return JSON.parse(localStorage.getItem(HELD_KEY) || '[]'); } catch { return []; } }
function saveHeld(l) { try { localStorage.setItem(HELD_KEY, JSON.stringify(l)); } catch {} }

/* ══════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
══════════════════════════════════════════════════════════════════════════ */
export default function POS({ sidebarOpen = true, onToggleSidebar }) {
  const { user } = useAuth();

  /* products & categories */
  const [allProducts,      setAllProducts]      = useState([]);
  const [categories,       setCategories]       = useState([]);
  const [selectedCat,      setSelectedCat]      = useState(null);
  const [loading,          setLoading]          = useState(true);

  /* search / barcode */
  const [query,            setQuery]            = useState('');
  const searchRef                               = useRef(null);
  const [showProducts,     setShowProducts]     = useState(false); // product picker overlay

  /* cart */
  const [cart,             setCart]             = useState([]);

  /* payment */
  const [payMethod,        setPayMethod]        = useState('cash');
  const [creditCustomer,   setCreditCustomer]   = useState(null);

  /* discount */
  const [cartonMode,       setCartonMode]       = useState(false);
  const [cartonDiscountPercent, setCartonDiscountPercent] = useState(0);

  /* customer picker */
  const [custDialog,       setCustDialog]       = useState(false);
  const [customers,        setCustomers]        = useState([]);
  const [custSearch,       setCustSearch]       = useState('');

  /* held */
  const [heldInvoices,     setHeldInvoices]     = useState(loadHeld);
  const [heldDialog,       setHeldDialog]       = useState(false);

  /* returns */
  const [returnsOpen,      setReturnsOpen]      = useState(false);

  /* sale */
  const [submitting,       setSubmitting]       = useState(false);
  const [lastInvoice,      setLastInvoice]      = useState(null);

  /* clock */
  const [now,              setNow]              = useState(new Date());

  /* ── boot ──────────────────────────────────────────────────────────── */
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(t);
  }, []);

  const refreshProducts = useCallback(async () => {
    try {
      const response = await api.get('/pos/products', { params: { limit: 500 } });
      setAllProducts(response.data || []);
    } catch {
      // Keep the last known catalog visible if a background refresh is unavailable.
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get('/pos/products', { params: { limit: 500 } }),
      api.get('/categories'),
      api.get('/pos/settings'),
    ]).then(([pr, cr, sr]) => {
      setAllProducts(pr.data || []);
      setCategories(cr.data || []);
      setCartonDiscountPercent(Number(sr.data.carton_discount_percent) || 0);
    }).catch(() => {}).finally(() => setLoading(false));

    const refreshOnFocus = () => refreshProducts();
    const interval = window.setInterval(refreshProducts, 5000);
    window.addEventListener('focus', refreshOnFocus);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('focus', refreshOnFocus);
    };
  }, [refreshProducts]);

  useEffect(() => {
    if (custDialog) {
      api.get('/customers', { params: { q: custSearch || undefined } })
        .then((r) => setCustomers(r.data)).catch(() => {});
    }
  }, [custDialog, custSearch]);

  /* ── derived products ───────────────────────────────────────────────── */
  const displayProducts = useMemo(() => {
    let list = allProducts;
    const q = query.trim().toLowerCase();
    if (q) {
      list = list.filter((p) =>
        (p.name || '').toLowerCase().includes(q) ||
        (p.sku  || '').toLowerCase().includes(q) ||
        (p.barcode || '').toLowerCase().includes(q),
      );
    } else if (selectedCat) {
      list = list.filter((p) => p.category_id === selectedCat);
    } else {
      const feat = list.filter((p) => p.is_featured);
      const rest = list.filter((p) => !p.is_featured);
      list = [...feat, ...rest];
    }
    return list;
  }, [allProducts, query, selectedCat]);

  const featuredProducts = useMemo(
    () => allProducts
      .filter((product) => product.is_featured && product.is_active !== false)
      .sort((a, b) => (
        Number(a.featured_order || 0) - Number(b.featured_order || 0) ||
        String(a.name || '').localeCompare(String(b.name || ''), 'ar')
      )),
    [allProducts],
  );

  /* ── cart helpers ───────────────────────────────────────────────────── */
  const addToCart = useCallback((p) => {
    const piecesPerCarton = Math.max(1, Number(p.pieces_per_carton) || 1);
    const saleUnit = cartonMode ? 'carton' : 'piece';
    const stockPerUnit = cartonMode ? piecesPerCarton : 1;
    const stock = Number(p.current_stock ?? 0);
    if (stock <= 0) {
      toast({ title: '⛔ نفد المخزون', description: `"${p.name}" غير متوفر`, variant: 'destructive' }); return;
    }
    const existQ = cart.find((x) => x.product_id === p.id)?.quantity || 0;
    if ((existQ + 1) * stockPerUnit > stock) {
      toast({ title: '⚠️ تجاوز المخزون', description: 'المخزون لا يكفي لوحدة البيع المختارة', variant: 'destructive' }); return;
    }
    setCart((prev) => {
      const idx = prev.findIndex((x) => x.product_id === p.id);
      if (idx >= 0) {
        const c = [...prev];
        c[idx] = { ...c[idx], quantity: c[idx].quantity + 1, sale_unit: saleUnit, pieces_per_carton: piecesPerCarton };
        return c;
      }
      return [...prev, {
        product_id: p.id, name: p.name, sku: p.sku, unit: p.unit,
        quantity: 1, unit_price: Number(p.sale_price), stock,
        sale_unit: saleUnit, pieces_per_carton: piecesPerCarton,
      }];
    });
    setShowProducts(false);
    setQuery('');
  }, [cart, cartonMode]);

  const updateQty = (idx, delta) => setCart((prev) => {
    const c = [...prev]; const item = c[idx]; const max = Math.floor(Number(item.stock || 0) / (item.sale_unit === 'carton' ? (item.pieces_per_carton || 1) : 1));
    const q = Math.min(max, item.quantity + delta);
    if (q <= 0) return c.filter((_, i) => i !== idx);
    c[idx] = { ...c[idx], quantity: q }; return c;
  });

  const setQtyDirect = (idx, val) => {
    const q = Number(val); if (isNaN(q) || q < 0) return;
    if (q === 0) setCart((prev) => prev.filter((_, i) => i !== idx));
    else setCart((prev) => {
      const c = [...prev];
      const item = c[idx];
      const max = Math.floor(Number(item.stock || 0) / (item.sale_unit === 'carton' ? (item.pieces_per_carton || 1) : 1));
      c[idx] = { ...item, quantity: Math.min(q, max) };
      return c;
    });
  };

  const removeItem = (idx) => setCart((prev) => prev.filter((_, i) => i !== idx));
  const clearCart  = () => { if (window.confirm('مسح السلة كاملاً؟')) { setCart([]); } };

  /* ── barcode search ─────────────────────────────────────────────────── */
  const handleSearch = async (val) => {
    setQuery(val);
    if (!val.trim()) { setShowProducts(false); return; }
    setShowProducts(true);
    // Try barcode lookup if looks like barcode (no spaces, ≥6 chars)
    if (val.trim().length >= 6 && !val.includes(' ')) {
      try {
        const { data } = await api.get(`/products/by-barcode/${encodeURIComponent(val.trim())}`);
        addToCart(data);
        setQuery('');
        setShowProducts(false);
      } catch { /* not a barcode, show search results */ }
    }
  };

  /* ── held ───────────────────────────────────────────────────────────── */
  const holdInvoice = () => {
    if (!cart.length) { toast({ title: 'السلة فارغة', variant: 'destructive' }); return; }
    const held = {
      id: Date.now(), cart: [...cart], payMethod, creditCustomer,
      discountAmt: effectiveDiscount, cartonMode,
      savedAt: new Date().toISOString(), total,
    };
    const updated = [...heldInvoices, held]; setHeldInvoices(updated); saveHeld(updated);
    setCart([]); setCreditCustomer(null); setPayMethod('cash'); setCartonMode(false);
    toast({ title: `✅ تم تعليق الفاتورة` });
  };

  const resumeHeld = (held) => {
    if (cart.length > 0 && !window.confirm('السلة الحالية ستُستبدل. متابعة؟')) return;
    setCart(held.cart); setPayMethod(held.payMethod || 'cash'); setCreditCustomer(held.creditCustomer || null);
    setCartonMode(!!held.cartonMode);
    const updated = heldInvoices.filter((h) => h.id !== held.id); setHeldInvoices(updated); saveHeld(updated);
    setHeldDialog(false); toast({ title: 'تم استئناف الفاتورة' });
  };
  const discardHeld = (id) => {
    if (!window.confirm('حذف الفاتورة المعلقة؟')) return;
    const updated = heldInvoices.filter((h) => h.id !== id); setHeldInvoices(updated); saveHeld(updated);
  };

  /* ── payment ────────────────────────────────────────────────────────── */
  const onPaySelect = (v) => {
    setPayMethod(v);
    if (v === 'credit') {
      if (!cart.length) { toast({ title: 'أضف منتجاً أولاً', variant: 'destructive' }); return; }
      setCustDialog(true);
    } else { setCreditCustomer(null); }
  };

  /* ── totals ─────────────────────────────────────────────────────────── */
  const grossSubtotal = cart.reduce((s, it) =>
    s + it.quantity * it.unit_price * (it.sale_unit === 'carton' ? (it.pieces_per_carton || 1) : 1), 0);
  const cartonSubtotal = cart.reduce((s, it) =>
    s + (it.sale_unit === 'carton' ? it.quantity * it.unit_price * (it.pieces_per_carton || 1) : 0), 0);
  const effectiveDiscount = cartonMode
    ? cartonSubtotal * (cartonDiscountPercent / 100)
    : 0;
  const subtotal   = grossSubtotal;
  const total      = Math.max(0, grossSubtotal - effectiveDiscount);
  const totalQty   = cart.reduce((s, it) => s + it.quantity, 0);
  const canComplete = cart.length > 0 && !(payMethod === 'credit' && !creditCustomer);
  const activePayment = PAYMENT_METHODS.find((p) => p.v === payMethod);

  /* ── complete sale ──────────────────────────────────────────────────── */
  const completeSale = async () => {
    if (!cart.length) { toast({ title: 'السلة فارغة', variant: 'destructive' }); return; }
    if (payMethod === 'credit' && !creditCustomer) { toast({ title: 'اختر عميلاً', variant: 'destructive' }); return; }
    setSubmitting(true);
    try {
      const { data } = await api.post('/sales', {
        customer_id: payMethod === 'credit' ? creditCustomer.id : null,
        items: cart.map((c) => ({
          product_id: c.product_id, quantity: c.quantity, unit_price: c.unit_price,
          sale_unit: c.sale_unit || 'piece', pieces_per_carton: c.pieces_per_carton || 1,
        })),
        payment_method: payMethod,
        discount_amount: effectiveDiscount,
      });
      setLastInvoice(data);
      toast({ title: '✅ تم البيع', description: `${data.invoice_no} — ${fmt(data.total)} ر.ي` });
      setCart([]); setCreditCustomer(null); setPayMethod('cash'); setCartonMode(false);
      api.get('/pos/products', { params: { limit: 500 } }).then((r) => setAllProducts(r.data)).catch(() => {});
      searchRef.current?.focus();
    } catch (e) {
      toast({ title: 'فشل البيع', description: formatApiError(e), variant: 'destructive' });
    } finally { setSubmitting(false); }
  };

  /* ═══════════════════════════════════════════════════════════════════
     RENDER
  ═══════════════════════════════════════════════════════════════════ */
  return (
    <div
      dir="rtl"
      data-testid="pos-page"
      className="flex min-h-0 flex-col overflow-hidden bg-[#eef3f8] text-slate-900"
      style={{ height: 'calc(100vh - 60px)' }}
    >
      <div className="flex h-14 flex-shrink-0 items-center justify-between border-b border-[#19395f] bg-[#102d50] px-5 text-white shadow-lg">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/15">
            <ShoppingBasket className="h-5 w-5 text-sky-300" />
          </div>
          <div>
            <p className="text-sm font-extrabold tracking-wide">ميني ماركت الفنية</p>
            <p className="text-[10px] text-slate-300">نقطة البيع الذكية</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="hidden rounded-full bg-white/10 px-3 py-1.5 text-slate-200 sm:inline-flex">الفرع الرئيسي</span>
          <span className="rounded-full bg-emerald-500/15 px-3 py-1.5 font-bold text-emerald-200">{user?.full_name || user?.username || 'الكاشير'}</span>
          <span className="hidden text-slate-300 sm:inline">{now.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>

      <div dir="ltr" className="flex min-h-0 flex-1 flex-col gap-4 p-4 md:flex-row">
        {/* Product workspace — left side visually, no stock quantities exposed. */}
        <section dir="rtl" className="order-2 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white p-4 shadow-[0_18px_45px_rgba(15,45,80,0.10)] md:order-1" data-testid="featured-products-panel">
          <div className="mb-3 flex flex-shrink-0 items-center justify-between">
            <div>
              <p className="text-xs font-bold text-sky-600">البيع السريع</p>
              <h1 className="text-xl font-black text-[#102d50]">المنتجات المميزة</h1>
            </div>
            <Badge className="border border-sky-100 bg-sky-50 text-sky-700">{featuredProducts.length}</Badge>
          </div>

          <div className="relative mb-3 flex-shrink-0">
            <div className="flex h-12 items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 transition focus-within:border-sky-400 focus-within:ring-4 focus-within:ring-sky-100" dir="ltr">
              <ScanLine className="h-5 w-5 flex-shrink-0 text-sky-600" />
              <div className="relative flex-1" dir="rtl">
                <Search className="pointer-events-none absolute right-0 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  ref={searchRef}
                  value={query}
                  onChange={(e) => handleSearch(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Escape') { setQuery(''); setShowProducts(false); } }}
                  placeholder="امسح الباركود أو ابحث باسم المنتج / SKU"
                  className="h-10 w-full bg-transparent pr-7 pl-2 text-sm font-semibold text-slate-800 outline-none placeholder:text-slate-400"
                  dir="rtl"
                  data-testid="pos-barcode-input"
                  autoComplete="off"
                />
                {query && <button type="button" onClick={() => { setQuery(''); setShowProducts(false); }} className="absolute left-0 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"><X className="h-4 w-4" /></button>}
              </div>
              <span className="hidden rounded-lg bg-white px-2 py-1 text-[10px] font-bold text-slate-400 shadow-sm sm:inline">F2</span>
            </div>
            {showProducts && (
              <div className="absolute inset-x-0 top-full z-50 mt-2 max-h-80 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
                <div className="max-h-72 overflow-y-auto">
                  {loading && <div className="py-8 text-center text-sm text-slate-400">جارٍ التحميل...</div>}
                  {!loading && displayProducts.length === 0 && <div className="py-8 text-center text-sm text-slate-400">لا توجد نتائج</div>}
                  {displayProducts.map((p) => {
                    const oos = Number(p.current_stock) <= 0;
                    return <button key={p.id} type="button" onClick={() => addToCart(p)} disabled={oos} data-testid={`pos-product-${p.sku}`} className={`flex w-full items-center justify-between border-b border-slate-100 px-4 py-3 text-right transition ${oos ? 'cursor-not-allowed opacity-40' : 'hover:bg-sky-50'}`}>
                      <span className="min-w-0 flex-1 truncate text-sm font-bold text-slate-800">{p.name}</span>
                      <span className="mr-4 flex-shrink-0 text-sm font-black tabular-nums text-sky-700">{fmt(p.sale_price)} ر.ي</span>
                    </button>;
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="mb-3 flex items-center justify-between rounded-2xl border border-sky-100 bg-sky-50/70 px-4 py-2">
            <div className="flex items-center gap-2"><Star className="h-4 w-4 fill-amber-400 text-amber-400" /><span className="text-xs font-bold text-[#102d50]">اختيارات المتجر السريعة</span></div>
            <span className="text-[10px] font-semibold text-sky-600">اضغط لإضافة المنتج</span>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            {featuredProducts.length === 0 ? (
              <div className="flex h-full min-h-[220px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 text-center text-slate-400">
                <Star className="mb-3 h-10 w-10 text-slate-200" />
                <p className="text-sm font-bold">لا توجد منتجات مميزة</p>
                <p className="mt-1 text-xs">فعّل المنتج المميز من إدارة المنتجات ليظهر هنا</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                {featuredProducts.map((p) => {
                  const outOfStock = Number(p.current_stock || 0) <= 0;
                  return <button key={p.id} type="button" disabled={outOfStock} onClick={() => addToCart(p)} data-testid={`featured-product-${p.sku}`} className={`group flex min-h-[118px] flex-col justify-between rounded-2xl border bg-white p-3 text-right shadow-sm transition-all ${outOfStock ? 'cursor-not-allowed opacity-45' : 'border-slate-200 hover:-translate-y-0.5 hover:border-sky-400 hover:shadow-lg hover:shadow-sky-100 active:scale-[0.98]'}`}>
                    <div className="flex items-start justify-between gap-2"><p className="line-clamp-2 text-sm font-extrabold leading-5 text-[#102d50]">{p.name}</p><Star className="h-4 w-4 flex-shrink-0 fill-amber-400 text-amber-400" /></div>
                    <div className="mt-3 flex items-end justify-between gap-2"><span className="text-base font-black tabular-nums text-sky-700">{fmt(p.sale_price)} <small className="text-[10px] font-bold">ر.ي</small></span><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600"><Plus className="h-4 w-4" /></span></div>
                  </button>;
                })}
              </div>
            )}
          </div>
        </section>

        {/* Invoice workspace — right side. */}
        <section dir="rtl" className="order-1 flex min-h-0 w-full flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_18px_45px_rgba(15,45,80,0.12)] md:order-2 md:w-[430px] md:flex-shrink-0" data-testid="pos-invoice-panel">
          <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-100 bg-[#102d50] px-4 py-4 text-white">
            <div><p className="text-[10px] font-bold text-sky-200">فاتورة جديدة</p><h2 className="text-lg font-black">الفاتورة الحالية</h2></div>
            <div className="text-left"><p className="text-[10px] text-slate-300">رقم الفاتورة</p><p className="font-mono text-xs font-bold text-white">{lastInvoice ? lastInvoice.invoice_no : 'تلقائي'}</p></div>
          </div>
          <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-2 text-[11px] font-bold text-slate-500"><span>{cart.length} أصناف</span><span>{fmt(totalQty)} كمية</span><button type="button" onClick={clearCart} className="text-rose-500 hover:text-rose-700">مسح الفاتورة</button></div>

          <div className="grid flex-shrink-0 grid-cols-[1fr_58px_82px_28px] gap-2 border-b border-slate-100 px-4 py-2 text-[10px] font-black text-slate-400"><span>المنتج</span><span className="text-center">الكمية</span><span className="text-center">الإجمالي</span><span /></div>
          <div className="min-h-0 flex-1 overflow-y-auto px-3">
            {cart.length === 0 ? <div className="flex h-full min-h-[180px] flex-col items-center justify-center text-center text-slate-300"><Receipt className="mb-3 h-12 w-12" /><p className="text-sm font-bold text-slate-400">الفاتورة فارغة</p><p className="mt-1 text-xs">اختر منتجًا من القائمة</p></div> : cart.map((it, i) => {
              const lineTotal = it.quantity * it.unit_price * (it.sale_unit === 'carton' ? (it.pieces_per_carton || 1) : 1);
              return <div key={it.product_id} data-testid={`cart-item-${i}`} className="grid grid-cols-[1fr_58px_82px_28px] items-center gap-2 border-b border-slate-100 py-3">
                <div className="min-w-0"><p className="line-clamp-1 text-xs font-extrabold text-[#102d50]">{it.name}</p><p className="mt-1 text-[10px] text-slate-400">{fmt(it.unit_price)} ر.ي / {it.sale_unit === 'carton' ? 'كرتون' : 'قطعة'}</p></div>
                <div className="flex items-center justify-center gap-1"><button type="button" onClick={() => updateQty(i, -1)} className="flex h-6 w-6 items-center justify-center rounded-md border border-slate-200 text-slate-500 hover:border-sky-400 hover:text-sky-600"><Minus className="h-3 w-3" /></button><input type="number" value={it.quantity} onChange={(e) => setQtyDirect(i, e.target.value)} className="w-7 border-0 bg-transparent text-center text-xs font-black text-[#102d50] outline-none" min="0" /><button type="button" onClick={() => updateQty(i, 1)} className="flex h-6 w-6 items-center justify-center rounded-md border border-slate-200 text-slate-500 hover:border-sky-400 hover:text-sky-600"><Plus className="h-3 w-3" /></button></div>
                <p className="text-center text-xs font-black tabular-nums text-sky-700">{fmt(lineTotal)}</p>
                <button type="button" onClick={() => removeItem(i)} className="flex h-7 w-7 items-center justify-center rounded-lg text-rose-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 className="h-4 w-4" /></button>
              </div>;
            })}
          </div>

          <div className="flex-shrink-0 border-t border-slate-100 bg-slate-50 p-3">
            <div className="mb-2 flex items-center justify-between"><span className="text-xs font-bold text-slate-500">الإجمالي المستحق</span><span className="text-2xl font-black tabular-nums text-[#102d50]" data-testid="pos-total">{fmt(total)} <small className="text-xs">ر.ي</small></span></div>
            {effectiveDiscount > 0 && <div className="mb-2 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-700"><span>خصم الكرتون ({cartonDiscountPercent}%)</span><span>− {fmt(effectiveDiscount)} ر.ي</span></div>}
            <div className="mb-2 flex items-center justify-between gap-2"><span className="text-[11px] font-black text-slate-500">طريقة الدفع</span><button type="button" onClick={() => { const next = !cartonMode; setCartonMode(next); setCart((prev) => prev.map((item) => ({ ...item, sale_unit: next ? 'carton' : 'piece', pieces_per_carton: item.pieces_per_carton || 1 }))); }} data-testid="pos-carton-mode-toggle" className={`rounded-xl border px-2.5 py-1.5 text-[10px] font-black ${cartonMode ? 'border-orange-400 bg-orange-500 text-white' : 'border-slate-200 bg-white text-slate-500'}`}><Package className="ml-1 inline h-3.5 w-3.5" />بيع بالكرتون</button></div>
            <div className="grid grid-cols-4 gap-1.5">
              {PAYMENT_METHODS.map((pm) => { const Icon = pm.icon; const active = payMethod === pm.v; return <button key={pm.v} type="button" onClick={() => onPaySelect(pm.v)} data-testid={`pos-payment-${pm.v}`} className={`flex items-center justify-center gap-1 rounded-xl border px-1 py-2 text-[10px] font-black transition ${active ? 'border-sky-600 bg-sky-600 text-white shadow-md shadow-sky-200' : 'border-slate-200 bg-white text-slate-500 hover:border-sky-300 hover:text-sky-700'}`}><Icon className="h-3.5 w-3.5" />{pm.l}</button>; })}
            </div>
            {payMethod === 'credit' && <div className="mt-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2" data-testid="pos-credit-info">{creditCustomer ? <div className="flex items-center justify-between"><div><p className="text-xs font-black text-rose-700">{creditCustomer.full_name}</p><p className="text-[10px] text-rose-500">الرصيد بعد البيع: {fmt(Number(creditCustomer.balance) + total)} ر.ي</p></div><button type="button" onClick={() => setCustDialog(true)} className="text-[10px] font-bold text-rose-600 underline">تغيير</button></div> : <button type="button" onClick={() => setCustDialog(true)} className="flex w-full items-center justify-center gap-2 py-1 text-xs font-bold text-rose-600"><UserPlus className="h-4 w-4" />اختر عميلاً للبيع الآجل</button>}</div>}
            <div className="mt-3 grid grid-cols-3 gap-2"><button type="button" onClick={() => setReturnsOpen(true)} data-testid="pos-open-returns-btn" className="flex h-10 items-center justify-center gap-1 rounded-xl border border-rose-200 bg-white text-xs font-black text-rose-600 hover:bg-rose-50"><RotateCcw className="h-4 w-4" />استرجاع</button><button type="button" onClick={holdInvoice} className="flex h-10 items-center justify-center gap-1 rounded-xl border border-amber-200 bg-white text-xs font-black text-amber-600 hover:bg-amber-50"><PauseCircle className="h-4 w-4" />تعليق</button><button type="button" onClick={() => setHeldDialog(true)} className="relative flex h-10 items-center justify-center gap-1 rounded-xl border border-sky-200 bg-white text-xs font-black text-sky-700 hover:bg-sky-50"><PlayCircle className="h-4 w-4" />معلقة{heldInvoices.length > 0 && <span className="absolute -right-1 -top-2 flex h-5 min-w-5 items-center justify-center rounded-full bg-sky-600 px-1 text-[10px] text-white">{heldInvoices.length}</span>}</button></div>
            <button type="button" onClick={completeSale} disabled={submitting || !canComplete} data-testid="pos-complete-sale-btn" className={`mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-xl text-sm font-black text-white shadow-lg transition active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 ${canComplete ? 'bg-emerald-600 shadow-emerald-200 hover:bg-emerald-700' : 'bg-slate-300'}`}>{submitting ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />جارٍ الحفظ...</> : <><CheckCircle2 className="h-5 w-5" />إتمام الدفع {cart.length > 0 && <span>— {fmt(total)} ر.ي</span>}</>}</button>
          </div>
        </section>
      </div>

      {/* ══════ DIALOGS ═══════════════════════════════════════════════ */}

      {/* Returns */}
      <PosReturnsDialog
        open={returnsOpen}
        onClose={() => setReturnsOpen(false)}
        onCompleted={() => api.get('/pos/products', { params: { limit: 500 } }).then((r) => setAllProducts(r.data)).catch(() => {})}
      />

      {/* Held invoices */}
      <Dialog open={heldDialog} onOpenChange={setHeldDialog}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <PauseCircle className="w-5 h-5 text-yellow-400" />
              الفواتير المعلقة
              <Badge className="bg-yellow-400/15 text-yellow-300 border border-yellow-400/30">{heldInvoices.length}</Badge>
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
                      <p className="font-bold text-slate-900 text-sm">{held.cart.length} صنف</p>
                      <p className="text-xs text-slate-400">{new Date(held.savedAt).toLocaleString('ar-EG', { dateStyle: 'short', timeStyle: 'short' })}</p>
                    </div>
                    <p className="font-extrabold text-amber-600 text-lg">{fmt(held.total)} ر.ي</p>
                  </div>
                  <p className="text-xs text-slate-500 mb-2 line-clamp-1">{held.cart.map((i) => i.name).join(' · ')}</p>
                  <div className="flex gap-2">
                    <Button onClick={() => resumeHeld(held)} className="flex-1 h-8 bg-yellow-400 hover:bg-yellow-300 text-slate-900 text-xs font-bold">
                      <PlayCircle className="w-3.5 h-3.5 ml-1" /> استئناف
                    </Button>
                    <Button onClick={() => discardHeld(held.id)} variant="outline" className="h-8 border-rose-300 text-rose-500 hover:bg-rose-50 px-2.5">
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
      <Dialog open={custDialog} onOpenChange={setCustDialog}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserPlus className="w-5 h-5 text-sky-400" /> اختر عميل
            </DialogTitle>
          </DialogHeader>
          <div className="relative mb-2">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input autoFocus value={custSearch} onChange={(e) => setCustSearch(e.target.value)} placeholder="بحث بالاسم أو الهاتف..." className="pr-10" data-testid="pos-customer-search-input" />
          </div>
          <div className="max-h-96 overflow-y-auto space-y-1">
            {customers.length === 0
              ? <p className="text-center text-slate-400 py-6 text-sm">لا يوجد عملاء</p>
              : customers.map((c) => (
                <button key={c.id} onClick={() => { setCreditCustomer(c); setCustDialog(false); }} data-testid={`pos-customer-pick-${c.id}`}
                  className="w-full text-right p-3 rounded-xl border border-slate-200 hover:bg-rose-50 hover:border-rose-300 transition-all">
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="font-semibold text-slate-900 text-sm">{c.full_name}</p>
                      <p className="text-xs text-slate-500">{c.phone || '—'}</p>
                    </div>
                    <div className="text-left">
                      <p className="text-[9px] text-slate-400">رصيد</p>
                      <p className={`font-extrabold text-sm ${Number(c.balance) > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>{fmt(c.balance)} ر.ي</p>
                    </div>
                  </div>
                </button>
              ))
            }
          </div>
        </DialogContent>
      </Dialog>

    </div>
  );
}
