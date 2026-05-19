import { useEffect, useMemo, useRef, useState, ChangeEvent } from 'react';
import {
  ArrowLeft, Loader2, BarChart3, FlaskConical, Clock, AlertCircle, X, Upload,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import {
  listReports, getReport,
  type ReportListItem, type FullReport, type PerQuestionResult,
} from '../api/EvalApi';

interface EvalDashboardProps {
  onBack: () => void;
}

// Local extension of ReportListItem — uploaded reports carry the full payload
// in-memory so the drill-down modal can render them without a server round-trip.
type DashboardReport = ReportListItem & {
  _inline?: FullReport;
  _source: 'server' | 'upload';
};

// Try to make timestamp strings sortable & display-friendly.
function fmt(ts?: string): string {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString('tr-TR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return ts;
  }
}

// Compact label for the x-axis of trend charts.
function shortLabel(ts?: string, fallback?: string): string {
  if (!ts) return fallback?.slice(0, 16) ?? '—';
  try {
    const d = new Date(ts);
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  } catch {
    return ts.slice(0, 16);
  }
}

function setsEqual(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const x of a) if (!b.has(x)) return false;
  return true;
}

// Quick shape check for an uploaded JSON — the evaluator script always
// produces these keys, so a missing one means it isn't a real eval report.
function looksLikeEvalReport(obj: any): obj is FullReport {
  return !!(
    obj &&
    typeof obj === 'object' &&
    obj.summary &&
    obj.summary.retrieval &&
    obj.summary.generation &&
    Array.isArray(obj.results)
  );
}

export function EvalDashboard({ onBack }: EvalDashboardProps) {
  const [serverReports, setServerReports] = useState<ReportListItem[] | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [uploadedReports, setUploadedReports] = useState<DashboardReport[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // selectedFilenames is the live checkbox state.
  // appliedFilenames is what the charts filter on — only changes when the
  // user clicks "Karşılaştır", so the charts don't jitter on every click.
  const [selectedFilenames, setSelectedFilenames] = useState<Set<string>>(new Set());
  const [appliedFilenames, setAppliedFilenames] = useState<Set<string>>(new Set());
  const seenRef = useRef<Set<string>>(new Set());

  const [openReport, setOpenReport] = useState<FullReport | null>(null);
  const [openFilename, setOpenFilename] = useState<string | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Fetch server-side reports once on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await listReports();
        if (!cancelled) setServerReports(data);
      } catch (err: any) {
        if (!cancelled) setListError(err?.response?.data?.detail || err?.message || 'Raporlar yüklenemedi');
      } finally {
        if (!cancelled) setLoadingList(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Merge uploads + server reports. Uploaded reports come first so they're
  // visually prominent and easy to spot.
  const combinedReports: DashboardReport[] = useMemo(() => {
    const server: DashboardReport[] = (serverReports ?? []).map(r => ({
      ...r,
      _source: 'server',
    }));
    return [...uploadedReports, ...server];
  }, [uploadedReports, serverReports]);

  // When new reports arrive (initial fetch or a new upload), auto-add their
  // filenames to both selection sets so they show up in charts immediately.
  // Existing user selections are preserved.
  useEffect(() => {
    const newOnes = combinedReports.filter(r => !seenRef.current.has(r.filename));
    if (newOnes.length === 0) return;
    newOnes.forEach(r => seenRef.current.add(r.filename));
    setSelectedFilenames(prev => {
      const next = new Set(prev);
      newOnes.forEach(r => next.add(r.filename));
      return next;
    });
    setAppliedFilenames(prev => {
      const next = new Set(prev);
      newOnes.forEach(r => next.add(r.filename));
      return next;
    });
  }, [combinedReports]);

  const handleUploadClick = () => fileInputRef.current?.click();

  const handleUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      if (!looksLikeEvalReport(parsed)) {
        setUploadError(
          'JSON eval raporu şemasına uymuyor. ' +
          'summary.retrieval, summary.generation ve results alanları gerekli.'
        );
        return;
      }
      const filename = `uploaded:${file.name}`;
      const synthetic: DashboardReport = {
        filename,
        timestamp: parsed.timestamp,
        api_url: parsed.api_url,
        judge: parsed.judge,
        questions_file: parsed.questions_file,
        summary: parsed.summary,
        _inline: parsed,
        _source: 'upload',
      };
      // Replace any previous upload with the same name so re-uploading a file
      // refreshes it instead of duplicating.
      setUploadedReports(prev => [synthetic, ...prev.filter(r => r.filename !== filename)]);
      // Allow re-uploading the same file (otherwise onChange won't refire).
      seenRef.current.delete(filename);
    } catch (err: any) {
      setUploadError(err?.message || 'JSON okuma hatası');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const removeUpload = (filename: string) => {
    setUploadedReports(prev => prev.filter(r => r.filename !== filename));
    seenRef.current.delete(filename);
    setSelectedFilenames(prev => {
      const next = new Set(prev);
      next.delete(filename);
      return next;
    });
    setAppliedFilenames(prev => {
      const next = new Set(prev);
      next.delete(filename);
      return next;
    });
  };

  const toggleSelection = (filename: string, checked: boolean) => {
    setSelectedFilenames(prev => {
      const next = new Set(prev);
      if (checked) next.add(filename); else next.delete(filename);
      return next;
    });
  };

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedFilenames(new Set(combinedReports.map(r => r.filename)));
    } else {
      setSelectedFilenames(new Set());
    }
  };

  const applyComparison = () => setAppliedFilenames(new Set(selectedFilenames));

  const openDetail = async (item: DashboardReport) => {
    setOpenFilename(item.filename);
    setOpenReport(null);
    setDetailError(null);
    if (item._inline) {
      // Uploaded report — render in-memory data, skip the server round-trip.
      setOpenReport(item._inline);
      return;
    }
    setLoadingDetail(true);
    try {
      const data = await getReport(item.filename);
      setOpenReport(data);
    } catch (err: any) {
      setDetailError(err?.response?.data?.detail || err?.message || 'Rapor yüklenemedi');
    } finally {
      setLoadingDetail(false);
    }
  };

  // Trend data — only the rows the user has applied to the comparison view.
  const trendData = useMemo(() => {
    const valid = combinedReports.filter(
      r => r.summary && !r.error && appliedFilenames.has(r.filename),
    );
    return [...valid].reverse().map(r => {
      const ret = r.summary!.retrieval;
      const gen = r.summary!.generation;
      return {
        label: shortLabel(r.timestamp, r.filename),
        s1_hit1: ret.stage1_vector?.['hit@1'] ?? null,
        s1_mrr: ret.stage1_vector?.mrr ?? null,
        s1_ndcg10: ret.stage1_vector?.['ndcg@10'] ?? null,
        s2_hit1: ret.stage2_full_pipeline?.['hit@1'] ?? null,
        s2_mrr: ret.stage2_full_pipeline?.mrr ?? null,
        s2_ndcg10: ret.stage2_full_pipeline?.['ndcg@10'] ?? null,
        faithfulness: gen.avg_faithfulness ?? null,
        answer_relevance: gen.avg_answer_relevance ?? null,
        context_precision: gen.avg_context_precision ?? null,
        context_recall: gen.avg_context_recall ?? null,
        latency_p95: r.summary?.retrieval?.latency?.p95_ms ?? null,
      };
    });
  }, [combinedReports, appliedFilenames]);

  const allSelected = combinedReports.length > 0 && selectedFilenames.size === combinedReports.length;
  const compareDirty = !setsEqual(selectedFilenames, appliedFilenames);
  const hasAny = combinedReports.length > 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#f8faf9]">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-[#e2e8e5] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3 max-w-[1200px] mx-auto w-full">
          <button onClick={onBack} className="p-2 rounded-lg hover:bg-[#f1f5f3] transition-colors">
            <ArrowLeft className="h-5 w-5 text-[#5f7068]" />
          </button>
          <div className="flex-1">
            <h1 className="text-[15px] font-semibold text-[#1a2e28]" style={{ fontFamily: 'var(--font-serif)' }}>
              Değerlendirme Panosu
            </h1>
            <p className="text-[11px] text-[#9aada2]">RAG hattının kayıtlı değerlendirme koşumları</p>
          </div>
          <button
            onClick={handleUploadClick}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#ecfdf5] hover:bg-[#d1fae5] border border-[#a7f3d0] text-[#047857] text-[12px] font-medium transition-colors"
          >
            <Upload className="h-3.5 w-3.5" />
            JSON yükle
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={handleUpload}
          />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[1200px] mx-auto px-6 py-6">
          {loadingList && (
            <div className="flex items-center gap-2 text-[#5f7068]">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Raporlar yükleniyor…</span>
            </div>
          )}

          {listError && (
            <div className="p-3 mb-6 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {listError}
            </div>
          )}

          {uploadError && (
            <div className="p-3 mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <div className="flex-1">{uploadError}</div>
              <button onClick={() => setUploadError(null)} className="text-red-700 hover:text-red-900">
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {!loadingList && !hasAny && !listError && (
            <div className="p-6 text-center text-[#5f7068] bg-white rounded-xl border border-[#e2e8e5]">
              Henüz değerlendirme raporu yok. Çalıştırmak için:
              <code className="block mt-2 text-[11px] font-mono bg-[#f1f5f3] p-2 rounded">
                docker compose run --rm backend python -m scripts.evaluate_api
              </code>
              <div className="mt-3 text-[11px] text-[#9aada2]">
                Veya yukarıdan elinizdeki bir JSON raporu yükleyin.
              </div>
            </div>
          )}

          {hasAny && (
            <div className="space-y-6">
              {/* IR metrics over time */}
              <ChartPanel title="Erişim metrikleri (zaman içinde)" icon={<BarChart3 className="h-4 w-4 text-[#047857]" />}>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8e5" />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} stroke="#9aada2" />
                    <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} stroke="#9aada2" />
                    <Tooltip contentStyle={{ fontSize: 11 }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="s1_hit1" name="Stage1 Hit@1" stroke="#94a3b8" dot={false} strokeWidth={1.5} />
                    <Line type="monotone" dataKey="s1_mrr" name="Stage1 MRR" stroke="#cbd5e1" dot={false} strokeWidth={1.5} />
                    <Line type="monotone" dataKey="s2_hit1" name="Stage2 Hit@1" stroke="#047857" dot={{ r: 3 }} strokeWidth={2} />
                    <Line type="monotone" dataKey="s2_mrr" name="Stage2 MRR" stroke="#10b981" dot={{ r: 3 }} strokeWidth={2} />
                    <Line type="monotone" dataKey="s2_ndcg10" name="Stage2 nDCG@10" stroke="#34d399" dot={{ r: 3 }} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartPanel>

              {/* Generation quality (LLM-judge scores) */}
              <ChartPanel title="Üretim kalitesi (LLM-jüri, 1–5 ölçek)" icon={<FlaskConical className="h-4 w-4 text-[#047857]" />}>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8e5" />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} stroke="#9aada2" />
                    <YAxis domain={[1, 5]} tick={{ fontSize: 10 }} stroke="#9aada2" />
                    <Tooltip contentStyle={{ fontSize: 11 }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="faithfulness"      name="Faithfulness"      stroke="#047857" dot={{ r: 3 }} strokeWidth={2} />
                    <Line type="monotone" dataKey="answer_relevance"  name="Answer Relevance"  stroke="#10b981" dot={{ r: 3 }} strokeWidth={2} />
                    <Line type="monotone" dataKey="context_precision" name="Context Precision" stroke="#f59e0b" dot={{ r: 3 }} strokeWidth={2} />
                    <Line type="monotone" dataKey="context_recall"    name="Context Recall"    stroke="#3b82f6" dot={{ r: 3 }} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartPanel>

              {/* Latency trend */}
              <ChartPanel title="Erişim p95 gecikmesi (ms)" icon={<Clock className="h-4 w-4 text-[#047857]" />}>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8e5" />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} stroke="#9aada2" />
                    <YAxis tick={{ fontSize: 10 }} stroke="#9aada2" />
                    <Tooltip contentStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="latency_p95" name="p95 ms" stroke="#047857" dot={{ r: 3 }} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartPanel>

              {/* Table of runs */}
              <div className="bg-white rounded-xl border border-[#e2e8e5] overflow-hidden">
                <div className="px-4 py-3 bg-[#f1f5f3] border-b border-[#e2e8e5] flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-[13px] font-semibold text-[#1a2e28]">
                    Koşum geçmişi ({combinedReports.length})
                  </h3>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-[#5f7068] tabular-nums">
                      {appliedFilenames.size} / {combinedReports.length} koşum grafikte
                    </span>
                    <button
                      onClick={applyComparison}
                      disabled={!compareDirty || selectedFilenames.size === 0}
                      className="text-[11px] font-medium text-white bg-[#047857] hover:bg-[#065f46] disabled:bg-[#d4ddd8] disabled:cursor-not-allowed px-3 py-1 rounded transition-colors"
                    >
                      {compareDirty ? 'Karşılaştır' : 'Uygulandı'}
                    </button>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead className="bg-[#f8faf9] border-b border-[#e2e8e5] text-[10px] uppercase tracking-wider text-[#9aada2]">
                      <tr>
                        <th className="px-3 py-2 w-8">
                          <input
                            type="checkbox"
                            aria-label="Tümünü seç"
                            checked={allSelected}
                            onChange={(e) => toggleSelectAll(e.target.checked)}
                            className="cursor-pointer accent-[#047857]"
                          />
                        </th>
                        <th className="text-left px-4 py-2">Tarih</th>
                        <th className="text-left px-4 py-2">Kaynak</th>
                        <th className="text-left px-4 py-2">Jüri</th>
                        <th className="text-right px-4 py-2">Hit@1 (S2)</th>
                        <th className="text-right px-4 py-2">MRR (S2)</th>
                        <th className="text-right px-4 py-2">Faithfulness</th>
                        <th className="text-right px-4 py-2">Ctx Precision</th>
                        <th className="text-right px-4 py-2">p95 ms</th>
                        <th className="text-right px-4 py-2"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#e2e8e5]">
                      {combinedReports.map((r) => {
                        const s = r.summary;
                        const isSelected = selectedFilenames.has(r.filename);
                        const isApplied = appliedFilenames.has(r.filename);
                        const rowBase = r._source === 'upload' ? 'bg-emerald-50/40' : '';
                        const rowDim = !isApplied ? 'opacity-50' : '';
                        if (!s) {
                          return (
                            <tr key={r.filename} className={`bg-red-50/40 ${rowDim}`}>
                              <td className="px-3 py-2">
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={(e) => toggleSelection(r.filename, e.target.checked)}
                                  className="cursor-pointer accent-[#047857]"
                                />
                              </td>
                              <td className="px-4 py-2 text-[#5f7068]">{r.filename}</td>
                              <td colSpan={8} className="px-4 py-2 text-red-700">
                                {r.error || 'Özet yok'}
                              </td>
                            </tr>
                          );
                        }
                        return (
                          <tr key={r.filename} className={`hover:bg-[#f8faf9] transition-colors ${rowBase} ${rowDim}`}>
                            <td className="px-3 py-2">
                              <input
                                type="checkbox"
                                aria-label={`Seç ${r.filename}`}
                                checked={isSelected}
                                onChange={(e) => toggleSelection(r.filename, e.target.checked)}
                                className="cursor-pointer accent-[#047857]"
                              />
                            </td>
                            <td className="px-4 py-2 text-[#1a2e28]">{fmt(r.timestamp)}</td>
                            <td className="px-4 py-2">
                              {r._source === 'upload' ? (
                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  yerel
                                  <button
                                    onClick={() => removeUpload(r.filename)}
                                    className="hover:text-emerald-900"
                                    aria-label="Kaldır"
                                    title="Kaldır"
                                  >
                                    <X className="h-3 w-3" />
                                  </button>
                                </span>
                              ) : (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#f1f5f3] text-[#5f7068] border border-[#e2e8e5]">
                                  sunucu
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-[#5f7068] truncate max-w-[200px]">
                              {r.judge ? `${r.judge.provider} · ${r.judge.model}` : '—'}
                            </td>
                            <td className="px-4 py-2 text-right tabular-nums">
                              {(s.retrieval.stage2_full_pipeline?.['hit@1'] ?? 0).toFixed(3)}
                            </td>
                            <td className="px-4 py-2 text-right tabular-nums">
                              {(s.retrieval.stage2_full_pipeline?.mrr ?? 0).toFixed(3)}
                            </td>
                            <td className="px-4 py-2 text-right tabular-nums">
                              {(s.generation.avg_faithfulness ?? 0).toFixed(2)}
                            </td>
                            <td className="px-4 py-2 text-right tabular-nums">
                              {(s.generation.avg_context_precision ?? 0).toFixed(2)}
                            </td>
                            <td className="px-4 py-2 text-right tabular-nums text-[#5f7068]">
                              {s.retrieval.latency?.p95_ms?.toFixed(0) ?? '—'}
                            </td>
                            <td className="px-4 py-2 text-right">
                              <button
                                onClick={() => openDetail(r)}
                                className="text-[11px] font-medium text-[#047857] hover:underline"
                              >
                                İncele →
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Drill-down modal */}
      {openFilename && (
        <RunDetailModal
          filename={openFilename}
          report={openReport}
          loading={loadingDetail}
          error={detailError}
          onClose={() => { setOpenFilename(null); setOpenReport(null); setDetailError(null); }}
        />
      )}
    </div>
  );
}

function ChartPanel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-[#e2e8e5] overflow-hidden">
      <div className="px-4 py-3 bg-[#f1f5f3] border-b border-[#e2e8e5] flex items-center gap-2">
        {icon}
        <h3 className="text-[13px] font-semibold text-[#1a2e28]">{title}</h3>
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}

function RunDetailModal({
  filename, report, loading, error, onClose,
}: {
  filename: string;
  report: FullReport | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  // Worst-faithfulness questions float to the top for the "what's broken" view.
  const sortedResults = useMemo<PerQuestionResult[]>(() => {
    if (!report?.results) return [];
    const score = (r: PerQuestionResult) => r.generation?.judge_scores?.faithfulness ?? 5;
    return [...report.results].sort((a, b) => score(a) - score(b));
  }, [report]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-xl w-full max-w-[900px] max-h-[85vh] flex flex-col shadow-2xl">
        <div className="px-5 py-3 border-b border-[#e2e8e5] flex items-center gap-3">
          <FlaskConical className="h-4 w-4 text-[#047857]" />
          <h2 className="text-[13px] font-semibold text-[#1a2e28] truncate flex-1" title={filename}>
            {filename}
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-[#f1f5f3]">
            <X className="h-4 w-4 text-[#5f7068]" />
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center gap-2 text-[#5f7068]">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Rapor yükleniyor…</span>
            </div>
          )}
          {error && (
            <div className="p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl">{error}</div>
          )}
          {report && (
            <>
              <div className="mb-4 grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px]">
                <KV label="Tarih" value={fmt(report.timestamp)} />
                <KV label="Jüri" value={report.judge ? `${report.judge.provider} · ${report.judge.model}` : '—'} />
                <KV label="Soru sayısı" value={String(report.results?.length ?? 0)} />
                <KV label="top_k" value={String(report.top_k ?? '—')} />
              </div>

              <h3 className="text-[12px] font-semibold text-[#1a2e28] mb-2">
                En düşük faithfulness skoruna göre sıralı sorular
              </h3>
              <div className="border border-[#e2e8e5] rounded-lg divide-y divide-[#e2e8e5]">
                {sortedResults.slice(0, 25).map((q) => {
                  const f = q.generation?.judge_scores?.faithfulness;
                  const ar = q.generation?.judge_scores?.answer_relevance;
                  const cp = q.generation?.judge_scores?.context_precision;
                  return (
                    <div key={q.id} className="px-3 py-2.5 hover:bg-[#f8faf9]">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-mono text-[#9aada2]">#{q.id}</span>
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${scoreClass(f)}`}>
                          F: {f?.toFixed(2) ?? '—'}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-50 text-gray-600">
                          AR: {ar?.toFixed(2) ?? '—'}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-50 text-gray-600">
                          CP: {cp?.toFixed(2) ?? '—'}
                        </span>
                      </div>
                      <p className="text-[12px] text-[#1a2e28] line-clamp-2">{q.question}</p>
                      {q.ground_truth && (
                        <p className="mt-1 text-[11px] text-[#5f7068] line-clamp-1">
                          <span className="font-medium">Beklenen:</span> {q.ground_truth}
                        </p>
                      )}
                      {q.generation?.answer && (
                        <p className="mt-1 text-[11px] text-[#5f7068] line-clamp-2">
                          <span className="font-medium">Yanıt:</span> {q.generation.answer}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#f8faf9] border border-[#e2e8e5] rounded px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-[#9aada2]">{label}</div>
      <div className="text-[12px] text-[#1a2e28] truncate">{value}</div>
    </div>
  );
}

function scoreClass(score?: number): string {
  if (score == null) return 'bg-gray-50 text-gray-500';
  if (score >= 4.5) return 'text-emerald-700 bg-emerald-50';
  if (score >= 3.5) return 'text-amber-700 bg-amber-50';
  return 'text-red-700 bg-red-50';
}
