import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock3, RefreshCw, XCircle } from 'lucide-react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import api, { formatApiError } from '../lib/api';
import { toast } from '../hooks/use-toast';

const dateText = (value) => value ? new Date(value).toLocaleString('ar-EG') : '—';
const pretty = (value) => JSON.stringify(value, null, 2);

export default function SyncConflicts() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState('pending');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/sync/conflicts', { params: { status: filter } });
      setItems(data || []);
    } catch (error) {
      toast({ title: 'تعذر تحميل تعارضات المزامنة', description: formatApiError(error), variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const resolve = async (item, resolution) => {
    setBusy(`${item._id}:${resolution}`);
    try {
      await api.post(`/sync/conflicts/${item._id}/resolve`, { resolution });
      toast({ title: resolution === 'local' ? 'تم اعتماد النسخة المحلية' : 'تم الإبقاء على نسخة Neon' });
      await load();
    } catch (error) {
      toast({ title: 'فشل حل التعارض', description: formatApiError(error), variant: 'destructive' });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6" dir="rtl" data-testid="sync-conflicts-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-rose-100 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6 text-rose-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">تعارضات المزامنة</h1>
            <p className="text-sm text-slate-500">راجع الاختلافات بين نسخة Windows وNeon واختر النسخة المعتمدة.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant={filter === 'pending' ? 'default' : 'outline'} onClick={() => setFilter('pending')}>قيد المراجعة</Button>
          <Button variant={filter === 'resolved' ? 'default' : 'outline'} onClick={() => setFilter('resolved')}>المعالجة السابقة</Button>
          <Button variant="outline" onClick={load} disabled={loading} data-testid="refresh-conflicts">
            <RefreshCw className={`w-4 h-4 ml-1.5 ${loading ? 'animate-spin' : ''}`} /> تحديث
          </Button>
        </div>
      </div>

      {!loading && items.length === 0 && (
        <Card className="border-emerald-200 bg-emerald-50">
          <CardContent className="p-8 text-center text-emerald-800">
            <CheckCircle2 className="w-12 h-12 mx-auto mb-3" />
            لا توجد تعارضات {filter === 'pending' ? 'قيد المراجعة' : 'في هذا السجل'}.
          </CardContent>
        </Card>
      )}

      {items.map((item) => (
        <Card key={item._id} className="border-slate-200 shadow-sm" data-testid={`sync-conflict-${item._id}`}>
          <CardContent className="p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Badge className="bg-rose-100 text-rose-800 border-rose-200">{item.collection}</Badge>
                <span className="font-mono text-xs text-slate-500">{item.document_id}</span>
                {item.status === 'resolved'
                  ? <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200">تمت المعالجة: {item.resolution === 'local' ? 'المحلي' : 'Neon'}</Badge>
                  : <Badge className="bg-amber-100 text-amber-800 border-amber-200"><Clock3 className="w-3 h-3 ml-1 inline" />قيد المراجعة</Badge>}
              </div>
              <span className="text-xs text-slate-500">اكتُشف: {dateText(item.created_at)}</span>
            </div>

            <div className="grid lg:grid-cols-2 gap-4">
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-amber-900">نسخة Windows المحلية</h3>
                  {item.suggested_resolution === 'local' && <Badge className="bg-amber-200 text-amber-900">الاقتراح المحلي</Badge>}
                </div>
                <pre className="text-xs whitespace-pre-wrap overflow-auto max-h-64 text-slate-700">{pretty(item.local_document)}</pre>
              </div>
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-bold text-blue-900">نسخة Neon السحابية</h3>
                  {item.suggested_resolution === 'remote' && <Badge className="bg-blue-200 text-blue-900">الاقتراح السحابي</Badge>}
                </div>
                <pre className="text-xs whitespace-pre-wrap overflow-auto max-h-64 text-slate-700">{pretty(item.remote_document)}</pre>
              </div>
            </div>

            {item.status === 'pending' && (
              <div className="flex flex-wrap gap-2 pt-1">
                <Button className="bg-amber-600 hover:bg-amber-700 text-white" disabled={busy} onClick={() => resolve(item, 'local')}>
                  <CheckCircle2 className="w-4 h-4 ml-1.5" /> اعتماد نسخة Windows
                </Button>
                <Button variant="outline" className="border-blue-300 text-blue-700" disabled={busy} onClick={() => resolve(item, 'remote')}>
                  <XCircle className="w-4 h-4 ml-1.5" /> الإبقاء على نسخة Neon
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
