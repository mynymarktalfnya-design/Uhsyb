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
      className="flex flex-col md:flex-row min-h-0 overflow-hidden bg-[#0d0d1a] text-white"
      style={{ height: 'calc(100vh - 60px)' }}
    >
      {!sidebarOpen && (
        <aside
          className="order-2 md:order-none w-full md:w-[360px] lg:w-[390px] flex-shrink-0 border-t md:border-t-0 md:border-l border-amber-500/30 bg-[#101426] p-3"
          data-testid="featured-products-panel"
          aria-label="المنتجات المميزة"
        >
          <div className="flex h-full min-h-0 flex-col rounded-2xl border border-amber-500/50 bg-gradient-to-b from-slate-900 to-slate-950 p-3 shadow-2xl shadow-amber-950/20">
            <div className="mb-3 flex flex-shrink-0 items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/15 text-amber-400">
                  <Star className="h-5 w-5 fill-amber-400" />
                </div>
                <div>
                  <h2 className="text-base font-extrabold text-white">المنتجات المميزة</h2>
                  <p className="text-[10px] text-slate-500">إضافة سريعة إلى السلة</p>
                </div>
              </div>
              <Badge className="border border-amber-500/30 bg-amber-500/10 text-amber-300">
                {featuredProducts.length}
              </Badge>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
              {featuredProducts.length === 0 ? (
                <div className="flex h-full min-h-[180px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 px-5 text-center">
                  <Star className="mb-2 h-9 w-9 text-slate-700" />
                  <p className="text-sm font-bold text-slate-500">لا توجد منتجات مميزة</p>
                  <p className="mt-1 text-xs leading-5 text-slate-600">
                    فعّل «منتج مميز» من إدارة المنتجات ليظهر هنا تلقائياً
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2.5">
                  {featuredProducts.map((p) => {
                    const outOfStock = Number(p.current_stock || 0) <= 0;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        disabled={outOfStock}
                        onClick={() => addToCart(p)}
                        data-testid={`featured-product-${p.sku}`}
                        className={`group relative flex min-h-[190px] flex-col overflow-hidden rounded-xl border border-slate-700/80 bg-slate-900/80 p-2 text-right transition-all ${
                          outOfStock
                            ? 'cursor-not-allowed opacity-45'
                            : 'hover:-translate-y-0.5 hover:border-amber-400/70 hover:bg-slate-800 active:scale-[0.98]'
                        }`}
                      >
                        <span className="absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-lg bg-amber-500 text-slate-950 shadow-lg">
                          <Star className="h-3.5 w-3.5 fill-current" />
                        </span>
                        <div className="mb-2 flex min-h-[58px] items-center rounded-lg bg-slate-800/70 px-2">
                          <p className="line-clamp-3 text-xs font-bold leading-4 text-white">{p.name}</p>
                        </div>
                        <p className="mt-1 text-sm font-extrabold text-amber-400">{fmt(p.sale_price)} ر.ي</p>
                        <p className={`mt-0.5 text-[10px] font-semibold ${outOfStock ? 'text-rose-400' : 'text-emerald-400'}`}>
                          {outOfStock ? 'نفد المخزون' : `${fmt(p.current_stock)} متوفر`}
                        </p>
                        <span className="mt-auto flex items-center justify-center gap-1 rounded-lg border border-amber-500/30 bg-amber-500/10 py-1.5 text-xs font-extrabold text-amber-300">
                          <Plus className="h-3.5 w-3.5" /> إضافة
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </aside>
      )}
      <section className="min-w-0 flex-1 flex flex-col overflow-hidden">

      {/* ══════ INFO CHIPS ════════════════════════════════════════════ */}
      <div className="flex-shrink-0 flex gap-2 px-3 py-2 border-b border-slate-800/60">
        {/* Invoice # */}
        <div className="flex items-center gap-2 bg-slate-800/70 rounded-xl px-3 py-1.5 flex-1 min-w-0">
          <Receipt className="w-4 h-4 text-amber-400 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-[9px] text-slate-500 font-semibold leading-none">فاتورة #</p>
            <p className="text-xs font-extrabold text-white font-mono leading-tight truncate">
              {lastInvoice ? lastInvoice.invoice_no : '—'}
            </p>
          </div>
        </div>
        {/* Cashier */}
        <div className="flex items-center gap-2 bg-slate-800/70 rounded-xl px-3 py-1.5 flex-1 min-w-0">
          <User className="w-4 h-4 text-sky-400 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-[9px] text-slate-500 font-semibold leading-none">الكاشير</p>
            <p className="text-xs font-bold text-white leading-tight truncate">
              {user?.full_name || user?.username || '—'}
            </p>
          </div>
        </div>
        {/* Branch */}
        <div className="flex items-center gap-2 bg-slate-800/70 rounded-xl px-3 py-1.5 flex-1 min-w-0">
          <ShoppingBasket className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-[9px] text-slate-500 font-semibold leading-none">الفرع</p>
            <p className="text-xs font-bold text-white leading-tight truncate">الرئيسي</p>
          </div>
        </div>
      </div>

      {/* ══════ SEARCH ═══════════════════════════════════════════════ */}
      <div className="flex-shrink-0 px-3 py-2 relative">
        <div className="flex gap-2" dir="ltr">
          <button
            type="button"
            onClick={onToggleSidebar}
            data-testid="pos-sidebar-toggle"
            aria-label={sidebarOpen ? 'إخفاء القائمة الجانبية' : 'إظهار القائمة الجانبية'}
            title={sidebarOpen ? 'إخفاء القائمة الجانبية' : 'إظهار القائمة الجانبية'}
            className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 border transition-all active:scale-95 ${
              sidebarOpen
                ? 'bg-slate-800/80 border-slate-700/60 text-slate-300 hover:border-amber-500/60 hover:text-amber-300'
                : 'bg-amber-500 border-amber-400 text-slate-950 shadow-lg shadow-amber-900/30'
            }`}
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="relative flex-1" dir="rtl">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="ابحث بالاسم أو الباركود أو SKU"
              className="w-full h-11 pr-10 pl-3 bg-slate-800/80 border border-slate-700/60 rounded-xl text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-amber-500/60"
              dir="rtl"
              data-testid="pos-barcode-input"
              autoComplete="off"
            />
            {query && (
              <button onClick={() => { setQuery(''); setShowProducts(false); }} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <button
            onClick={() => { setShowProducts(!showProducts); setSelectedCat(null); setQuery(''); searchRef.current?.focus(); }}
            className="w-11 h-11 rounded-xl bg-amber-500 hover:bg-amber-400 flex items-center justify-center flex-shrink-0 transition-all active:scale-95 shadow-lg shadow-amber-900/30"
            title="مسح الباركود / اختر منتج"
          >
            <ScanLine className="w-5 h-5 text-slate-900" />
          </button>
        </div>

        {/* ── Product picker overlay ──────────────────────────────── */}
        {showProducts && (
          <div className="absolute right-3 left-3 top-full mt-1 z-50 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl shadow-black/60 overflow-hidden" style={{ maxHeight: 340 }}>
            {/* Category strip */}
            <div className="flex gap-1.5 px-3 pt-3 pb-2 overflow-x-auto border-b border-slate-800" style={{ scrollbarWidth: 'none' }}>
              <button
                onClick={() => setSelectedCat(null)}
                className={`flex-shrink-0 px-3 py-1 rounded-lg text-[11px] font-bold transition-all ${!selectedCat ? 'bg-amber-500 text-slate-900' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
              >
                الكل
              </button>
              {categories.map((cat, i) => {
                const pal = getCatPalette(i);
                return (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCat(selectedCat === cat.id ? null : cat.id)}
                    className={`flex-shrink-0 px-3 py-1 rounded-lg text-[11px] font-bold transition-all ${selectedCat === cat.id ? 'bg-amber-500 text-slate-900' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
                  >
                    {cat.name}
                  </button>
                );
              })}
            </div>
            {/* Product list */}
            <div className="overflow-y-auto" style={{ maxHeight: 260 }}>
              {loading && (
                <div className="flex items-center justify-center py-8 text-slate-500 text-sm">
                  <span className="w-4 h-4 border-2 border-amber-500/40 border-t-amber-500 rounded-full animate-spin ml-2" />
                  تحميل...
                </div>
              )}
              {!loading && displayProducts.length === 0 && (
                <div className="text-center py-8 text-slate-500 text-sm">لا توجد نتائج</div>
              )}
              {displayProducts.map((p) => {
                const oos = Number(p.current_stock) <= 0;
                return (
                  <button
                    key={p.id}
                    onClick={() => addToCart(p)}
                    disabled={oos}
                    data-testid={`pos-product-${p.sku}`}
                    className={`w-full flex items-center justify-between px-4 py-2.5 text-right border-b border-slate-800/60 transition-all active:scale-[0.99] ${
                      oos ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-800/80'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-white leading-snug truncate">{p.name}</p>
                      <p className="text-[10px] text-slate-500">{p.sku}</p>
                    </div>
                    <div className="text-left flex-shrink-0 mr-3">
                      <p className="text-sm font-extrabold text-amber-400 tabular-nums">{fmt(p.sale_price)}</p>
                      <p className={`text-[10px] font-semibold ${oos ? 'text-rose-400' : Number(p.current_stock) <= 3 ? 'text-amber-400' : 'text-slate-500'}`}>
                        {oos ? 'نفد' : `${fmt(p.current_stock)} متاح`}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ══════ CATEGORY TABS ════════════════════════════════════════ */}
      <div className="flex-shrink-0 px-3 pb-2">
        <div className="flex gap-2 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
          <button
            onClick={() => { setSelectedCat(null); setShowProducts(false); setQuery(''); }}
            className={`flex-shrink-0 flex flex-col items-center gap-1 p-2 rounded-xl min-w-[56px] transition-all border ${
              !selectedCat && !query ? 'border-amber-500/50 bg-amber-500/10' : 'border-slate-700/40 bg-slate-800/60 hover:border-slate-600'
            }`}
          >
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${!selectedCat && !query ? 'bg-amber-500' : 'bg-slate-700'}`}>
              <Tag className={`w-4 h-4 ${!selectedCat && !query ? 'text-slate-900' : 'text-slate-400'}`} />
            </div>
            <span className={`text-[9px] font-bold leading-none ${!selectedCat && !query ? 'text-amber-400' : 'text-slate-500'}`}>الكل</span>
          </button>

          {categories.map((cat, i) => {
            const pal = getCatPalette(i);
            const Icon = pal.icon;
            const active = selectedCat === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => { setSelectedCat(active ? null : cat.id); setShowProducts(false); setQuery(''); }}
                className={`flex-shrink-0 flex flex-col items-center gap-1 p-2 rounded-xl min-w-[56px] transition-all border ${
                  active ? 'border-amber-500/50 bg-amber-500/10' : 'border-slate-700/40 bg-slate-800/60 hover:border-slate-600'
                }`}
              >
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${active ? pal.bg : 'bg-slate-700'}`}>
                  <Icon className={`w-4 h-4 ${active ? 'text-white' : pal.text}`} />
                </div>
                <span className={`text-[9px] font-bold leading-none truncate max-w-[52px] ${active ? 'text-amber-400' : 'text-slate-500'}`}>
                  {cat.name}
                </span>
              </button>
            );
          })}

          {/* More categories button */}
          <button
            onClick={() => setShowProducts(true)}
            className="flex-shrink-0 flex flex-col items-center gap-1 p-2 rounded-xl min-w-[56px] border border-slate-700/40 bg-slate-800/60 hover:border-slate-600 transition-all"
          >
            <div className="w-9 h-9 rounded-xl bg-slate-700 flex items-center justify-center">
              <MoreHorizontal className="w-4 h-4 text-slate-400" />
            </div>
            <span className="text-[9px] font-bold text-slate-500">المزيد</span>
          </button>
        </div>
      </div>

      {/* ══════ CART TABLE ═══════════════════════════════════════════ */}
      {/* Table header */}
      <div className="flex-shrink-0 flex items-center gap-0 px-3 py-1.5 bg-slate-900/80 border-y border-slate-800/80 text-[10px] font-bold text-slate-500">
        <div className="w-8 flex-shrink-0" />
        <div className="flex-1 text-right">الصنف</div>
        <div className="w-28 text-center flex-shrink-0">الكمية</div>
        <div className="w-20 text-center flex-shrink-0">سعر البيع</div>
        <div className="w-20 text-center flex-shrink-0">الإجمالي</div>
      </div>

      {/* Scrollable cart rows */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {cart.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-700 py-8">
            <ShoppingCart className="w-16 h-16 mb-3 opacity-10" />
            <p className="text-sm font-medium text-slate-600">السلة فارغة</p>
            <p className="text-xs text-slate-700 mt-1">ابحث عن منتج أو امسح الباركود</p>
          </div>
        ) : (
          cart.map((it, i) => {
            const lineTotal = it.quantity * it.unit_price *
              (it.sale_unit === 'carton' ? (it.pieces_per_carton || 1) : 1);
            return (
              <div
                key={it.product_id}
                data-testid={`cart-item-${i}`}
                className={`flex items-center gap-0 px-3 py-2.5 border-b border-slate-800/50 ${i % 2 === 0 ? 'bg-transparent' : 'bg-slate-900/30'}`}
              >
                {/* Delete */}
                <div className="w-8 flex-shrink-0 flex items-center justify-center">
                  <button
                    onClick={() => removeItem(i)}
                    className="w-6 h-6 rounded-lg flex items-center justify-center text-rose-700 hover:text-rose-400 hover:bg-rose-900/30 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
                {/* Product name + SKU */}
                <div className="flex-1 min-w-0 text-right pr-1">
                  <p className="text-sm font-bold text-white leading-snug line-clamp-1">{it.name}</p>
                  <p className="text-[10px] text-slate-600 font-mono">
                    {it.sku} · {it.sale_unit === 'carton'
                      ? `كرتون (${it.pieces_per_carton || 1} قطعة)`
                      : 'قطعة'}
                  </p>
                </div>
                {/* Qty controls */}
                <div className="w-28 flex-shrink-0 flex items-center justify-center gap-1">
                  <button
                    onClick={() => updateQty(i, -1)}
                    className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-rose-500/80 border border-slate-700 hover:border-rose-500 text-slate-300 hover:text-white flex items-center justify-center transition-all active:scale-95"
                  >
                    <Minus className="w-3 h-3" />
                  </button>
                  <input
                    type="number"
                    value={it.quantity}
                    onChange={(e) => setQtyDirect(i, e.target.value)}
                    className="w-9 h-7 text-center text-sm font-extrabold bg-slate-800/80 text-amber-300 rounded-lg border border-slate-700/60 focus:outline-none focus:border-amber-500 tabular-nums"
                    min="0"
                  />
                  <button
                    onClick={() => updateQty(i, 1)}
                    className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-emerald-500/80 border border-slate-700 hover:border-emerald-500 text-slate-300 hover:text-white flex items-center justify-center transition-all active:scale-95"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                </div>
                {/* Unit price */}
                <div className="w-20 flex-shrink-0 text-center">
                  <p className="text-xs font-bold text-slate-300 tabular-nums">{fmt(it.unit_price)}</p>
                  <p className="text-[9px] text-slate-600">ريال</p>
                </div>
                {/* Line total */}
                <div className="w-20 flex-shrink-0 text-center">
                  <p className="text-sm font-extrabold text-amber-400 tabular-nums">{fmt(lineTotal)}</p>
                  <p className="text-[9px] text-slate-600">ريال</p>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ══════ BOTTOM FIXED SECTION ═════════════════════════════════ */}
      <div className="flex-shrink-0 border-t border-slate-800 bg-[#0d0d1a]">

        {/* ── Summary stats ─────────────────────────────────────────── */}
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-slate-800/60">
          {/* Items count */}
          <div className="flex-1 flex flex-col items-center bg-slate-900/60 rounded-xl py-2 border border-slate-800/60">
            <ShoppingBasket className="w-5 h-5 text-blue-400 mb-1" />
            <p className="text-[9px] text-slate-500 font-semibold">عدد الأصناف</p>
            <p className="text-base font-extrabold text-white tabular-nums">{cart.length}</p>
          </div>
          {/* Total qty */}
          <div className="flex-1 flex flex-col items-center bg-slate-900/60 rounded-xl py-2 border border-slate-800/60">
            <Boxes className="w-5 h-5 text-purple-400 mb-1" />
            <p className="text-[9px] text-slate-500 font-semibold">إجمالي الكمية</p>
            <p className="text-base font-extrabold text-white tabular-nums">{totalQty}</p>
          </div>
          {/* Total amount */}
          <div className="flex-[1.4] flex flex-col items-center bg-slate-900/60 rounded-xl py-2 border border-slate-800/60">
            <p className="text-[9px] text-slate-500 font-semibold mb-0.5">الإجمالي</p>
            <p className="text-xl font-extrabold tabular-nums leading-none" style={{ color: '#22c55e' }} data-testid="pos-total">
              {fmt(total)}
            </p>
            <p className="text-[9px] text-slate-500 mt-0.5">ريال</p>
          </div>
        </div>

        {/* ── Payment methods ────────────────────────────────────────── */}
        <div className="px-3 pt-2 pb-1">
          <div className="flex items-center justify-between mb-2 gap-2">
            <p className="text-[10px] font-bold text-slate-500 tracking-widest">طرق الدفع</p>
            <button
              type="button"
              onClick={() => {
                const next = !cartonMode;
                setCartonMode(next);
                setCart((prev) => prev.map((item) => ({
                  ...item,
                  sale_unit: next ? 'carton' : 'piece',
                  pieces_per_carton: item.pieces_per_carton || 1,
                })));
              }}
              data-testid="pos-carton-mode-toggle"
              className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-extrabold transition-all active:scale-95 ${
                cartonMode
                  ? 'bg-orange-500 text-white border-orange-400 shadow-lg shadow-orange-900/30'
                  : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:border-orange-500/60'
              }`}
            >
              <Package className="w-4 h-4" />
              بيع بالكرتون
              {cartonMode && <span className="text-[10px] bg-white/20 rounded-md px-1.5 py-0.5">{cartonDiscountPercent}% خصم</span>}
            </button>
          </div>
          {/* Row 1: 4 methods */}
          <div className="grid grid-cols-4 gap-2 mb-2">
            {PAYMENT_METHODS.slice(0, 4).map((pm) => {
              const Icon = pm.icon;
              const active = payMethod === pm.v;
              return (
                <button
                  key={pm.v}
                  onClick={() => onPaySelect(pm.v)}
                  data-testid={`pos-payment-${pm.v}`}
                  className={`relative flex flex-col items-center gap-2 py-3 rounded-2xl transition-all active:scale-95 border ${
                    active
                      ? `bg-gradient-to-br ${pm.grad} border-transparent shadow-xl`
                      : 'bg-slate-800/80 border-slate-700/50 hover:border-slate-500 hover:bg-slate-800'
                  }`}
                >
                  {active && <span className="absolute inset-0 rounded-2xl ring-2 ring-white/20 pointer-events-none" />}
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${active ? 'bg-white/20' : 'bg-slate-700/60'}`}>
                    <Icon className={`w-5 h-5 ${active ? 'text-white' : 'text-slate-300'}`} />
                  </div>
                  <span className={`text-xs font-extrabold leading-none ${active ? 'text-white' : 'text-slate-400'}`}>{pm.l}</span>
                </button>
              );
            })}
          </div>
          {/* Row 2: 3 methods */}
          <div className="grid grid-cols-3 gap-2">
            {PAYMENT_METHODS.slice(4).map((pm) => {
              const Icon = pm.icon;
              const active = payMethod === pm.v;
              return (
                <button
                  key={pm.v}
                  onClick={() => onPaySelect(pm.v)}
                  data-testid={`pos-payment-${pm.v}`}
                  className={`relative flex flex-col items-center gap-2 py-3 rounded-2xl transition-all active:scale-95 border ${
                    active
                      ? `bg-gradient-to-br ${pm.grad} border-transparent shadow-xl`
                      : 'bg-slate-800/80 border-slate-700/50 hover:border-slate-500 hover:bg-slate-800'
                  }`}
                >
                  {active && <span className="absolute inset-0 rounded-2xl ring-2 ring-white/20 pointer-events-none" />}
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${active ? 'bg-white/20' : 'bg-slate-700/60'}`}>
                    <Icon className={`w-5 h-5 ${active ? 'text-white' : 'text-slate-300'}`} />
                  </div>
                  <span className={`text-xs font-extrabold leading-none ${active ? 'text-white' : 'text-slate-400'}`}>{pm.l}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Credit customer info */}
        {payMethod === 'credit' && (
          <div className="mx-3 mb-1 bg-rose-950/60 border border-rose-500/30 rounded-xl px-3 py-2" data-testid="pos-credit-info">
            {creditCustomer ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-rose-200">{creditCustomer.full_name}</p>
                  <p className="text-[10px] text-rose-400">رصيد: {fmt(creditCustomer.balance)} ر.ي → {fmt(Number(creditCustomer.balance) + total)} ر.ي</p>
                </div>
                <button onClick={() => setCustDialog(true)} className="text-[10px] text-rose-400 underline">تغيير</button>
              </div>
            ) : (
              <button onClick={() => setCustDialog(true)} className="w-full flex items-center justify-center gap-2 text-sm text-rose-300 font-bold py-1 hover:text-rose-200">
                <UserPlus className="w-4 h-4" /> اختر عميلاً للبيع الآجل
              </button>
            )}
          </div>
        )}

        {/* Discount info */}
  {effectiveDiscount > 0 && (
          <div className="mx-3 mb-1 flex items-center justify-between bg-amber-900/30 border border-amber-500/30 rounded-xl px-3 py-1.5">
            <span className="text-xs text-amber-300 font-semibold">خصم الكرتون ({cartonDiscountPercent}%)</span>
            <div className="flex items-center gap-2">
              <span className="text-sm font-extrabold text-amber-400 tabular-nums">− {fmt(effectiveDiscount)} ر.ي</span>
            </div>
          </div>
        )}

        {/* ── Action buttons ─────────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-2 px-3 pt-2 pb-2">
          {/* استرجاع */}
          <button
            onClick={() => setReturnsOpen(true)}
            data-testid="pos-open-returns-btn"
            className="relative flex flex-col items-center gap-2 py-3 rounded-2xl bg-slate-800/80 border border-rose-800/60 hover:border-rose-500/70 hover:bg-rose-950/40 transition-all active:scale-95"
          >
            <div className="w-9 h-9 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center">
              <RotateCcw className="w-5 h-5 text-rose-400" />
            </div>
            <span className="text-xs font-extrabold text-rose-300 leading-none">استرجاع</span>
          </button>

          {/* تعليق فاتورة */}
          <button
            onClick={holdInvoice}
            className="relative flex flex-col items-center gap-2 py-3 rounded-2xl bg-slate-800/80 border border-amber-800/60 hover:border-amber-500/70 hover:bg-amber-950/40 transition-all active:scale-95"
          >
            <div className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
              <PauseCircle className="w-5 h-5 text-amber-400" />
            </div>
            <span className="text-xs font-extrabold text-amber-300 leading-none">تعليق فاتورة</span>
          </button>

          {/* اكمال فاتورة معلقة */}
          <button
            onClick={() => setHeldDialog(true)}
            className="relative flex flex-col items-center gap-2 py-3 rounded-2xl bg-slate-800/80 border border-emerald-800/60 hover:border-emerald-500/70 hover:bg-emerald-950/40 transition-all active:scale-95"
          >
            {heldInvoices.length > 0 && (
              <span className="absolute -top-2 -right-2 min-w-[20px] h-5 px-1.5 bg-emerald-400 text-slate-900 rounded-full text-[10px] font-extrabold flex items-center justify-center shadow-lg">
                {heldInvoices.length}
              </span>
            )}
            <div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <PlayCircle className="w-5 h-5 text-emerald-400" />
            </div>
            <span className="text-xs font-extrabold text-emerald-300 leading-none">اكمال معلقة</span>
          </button>
        </div>

        {/* ── Checkout bar ───────────────────────────────────────────── */}
        <div className="flex items-center gap-2 px-3 pb-3">
          {/* More button */}
          <button
            onClick={() => setShowProducts(true)}
            className="w-14 h-12 rounded-xl bg-slate-800 border border-slate-700/60 flex flex-col items-center justify-center gap-0.5 transition-all active:scale-95 flex-shrink-0"
          >
            <MoreHorizontal className="w-4 h-4 text-slate-400" />
            <span className="text-[9px] text-slate-500 font-bold">المزيد</span>
          </button>

          {/* Complete sale */}
          <button
            onClick={completeSale}
            disabled={submitting || !canComplete}
            data-testid="pos-complete-sale-btn"
            className={`flex-1 h-12 rounded-xl font-extrabold text-sm flex items-center justify-center gap-2 transition-all active:scale-[0.99] shadow-xl disabled:opacity-40 disabled:cursor-not-allowed ${
              canComplete
                ? 'bg-orange-500 hover:bg-orange-400 text-white shadow-orange-900/40'
                : 'bg-slate-800 text-slate-600 border border-slate-700'
            }`}
          >
            {submitting ? (
              <>
                <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                جارٍ الحفظ...
              </>
            ) : (
              <>
                <ShoppingCart className="w-5 h-5" />
                إتمام البيع
                {cart.length > 0 && <span className="mr-1 opacity-80">— {fmt(total)}</span>}
              </>
            )}
          </button>
        </div>
      </div>
      </section>

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
