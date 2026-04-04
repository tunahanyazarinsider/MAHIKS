import { useState } from 'react';
import { ArrowLeft, Search, Loader2, ChevronDown, ChevronUp, Filter, Zap, Clock, Layers, XCircle, CheckCircle } from 'lucide-react';
import axios from 'axios';

const BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

interface SubChunk {
  rank?: number;
  text: string;
  source: string;
  ce_score: number;
  similarity?: number;
  word_count?: number;
}

interface PipelineStats {
  vector_results: number;
  bm25_results: number;
  fused_chunks: number;
  total_sub_chunks: number;
  sub_chunk_words: number;
  sub_chunk_overlap: number;
  threshold: number;
  passed_threshold: number;
  rejected_by_threshold: number;
  final_sent_to_llm: number;
  total_words_to_llm: number;
  retrieval_time_ms: number;
}

interface RagDebugResult {
  query: string;
  pipeline: PipelineStats;
  final_sub_chunks: SubChunk[];
  rejected_sub_chunks: SubChunk[];
}

interface RagInfoScreenProps {
  onBack: () => void;
}

function ScoreBadge({ score, label }: { score: number; label: string }) {
  const pct = (score * 100).toFixed(1);
  const color = score >= 0.8 ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
    : score >= 0.5 ? 'text-amber-700 bg-amber-50 border-amber-200'
    : score >= 0.1 ? 'text-orange-700 bg-orange-50 border-orange-200'
    : 'text-red-700 bg-red-50 border-red-200';

  return (
    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${color}`}>
      {label}: {pct}%
    </span>
  );
}

export function RagInfoScreen({ onBack }: RagInfoScreenProps) {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<RagDebugResult | null>(null);
  const [showRejected, setShowRejected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!query.trim() || isLoading) return;
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`${BASE_URL}/api/rag/debug`, {
        question: query.trim(),
      }, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 60000,
      });
      setResult(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Bir hata oluştu');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#f8faf9]">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-[#e2e8e5] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3 max-w-[900px] mx-auto w-full">
          <button onClick={onBack} className="p-2 rounded-lg hover:bg-[#f1f5f3] transition-colors">
            <ArrowLeft className="h-5 w-5 text-[#5f7068]" />
          </button>
          <div>
            <h1 className="text-[15px] font-semibold text-[#1a2e28]" style={{ fontFamily: 'var(--font-serif)' }}>
              RAG Pipeline Debugger
            </h1>
            <p className="text-[11px] text-[#9aada2]">Sorgu girin ve retrieval sonuçlarını inceleyin</p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[900px] mx-auto px-6 py-6">
          {/* Search input */}
          <div className="flex gap-3 mb-6">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Test sorgusu girin..."
              disabled={isLoading}
              className="flex-1 px-4 py-3 rounded-xl bg-white border border-[#e2e8e5] focus:border-[#047857] focus:ring-2 focus:ring-[#047857]/10 outline-none text-[14px] text-[#1a2e28] placeholder:text-[#9aada2]"
            />
            <button
              onClick={handleSearch}
              disabled={!query.trim() || isLoading}
              className="px-5 py-3 rounded-xl bg-[#047857] hover:bg-[#065f46] disabled:bg-[#d4ddd8] text-white text-[13px] font-medium flex items-center gap-2 transition-all"
            >
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Ara
            </button>
          </div>

          {error && (
            <div className="p-3 mb-6 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl">
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-5">
              {/* Pipeline Stats */}
              <div className="bg-white rounded-xl border border-[#e2e8e5] overflow-hidden">
                <div className="px-4 py-3 bg-[#f1f5f3] border-b border-[#e2e8e5]">
                  <h3 className="text-[13px] font-semibold text-[#1a2e28]">Pipeline Özeti</h3>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-[#e2e8e5]">
                  {[
                    { icon: Search, label: 'Vektör Sonuç', value: result.pipeline.vector_results },
                    { icon: Search, label: 'BM25 Sonuç', value: result.pipeline.bm25_results },
                    { icon: Layers, label: 'Fusion Sonuç', value: result.pipeline.fused_chunks },
                    { icon: Layers, label: 'Alt-Parça', value: result.pipeline.total_sub_chunks },
                    { icon: CheckCircle, label: 'Eşik Geçen', value: result.pipeline.passed_threshold },
                    { icon: XCircle, label: 'Eşik Altı', value: result.pipeline.rejected_by_threshold },
                    { icon: Zap, label: 'LLM\'e Gönderilen', value: result.pipeline.final_sent_to_llm },
                    { icon: Clock, label: 'Süre', value: `${result.pipeline.retrieval_time_ms}ms` },
                  ].map((stat, i) => (
                    <div key={i} className="bg-white px-4 py-3">
                      <div className="flex items-center gap-1.5 mb-1">
                        <stat.icon className="h-3 w-3 text-[#9aada2]" />
                        <span className="text-[10px] text-[#9aada2] uppercase tracking-wider">{stat.label}</span>
                      </div>
                      <span className="text-[18px] font-semibold text-[#1a2e28] tabular-nums">{stat.value}</span>
                    </div>
                  ))}
                </div>
                {/* Config row */}
                <div className="px-4 py-2.5 bg-[#f8faf9] border-t border-[#e2e8e5] flex flex-wrap gap-4 text-[11px] font-mono text-[#5f7068]">
                  <span><Filter className="h-3 w-3 inline mr-1" />Eşik (threshold): <strong className="text-[#1a2e28]">{result.pipeline.threshold}</strong></span>
                  <span>Alt-parça: <strong className="text-[#1a2e28]">{result.pipeline.sub_chunk_words}</strong> kelime</span>
                  <span>Overlap: <strong className="text-[#1a2e28]">{result.pipeline.sub_chunk_overlap}</strong> kelime</span>
                  <span>LLM'e toplam: <strong className="text-[#1a2e28]">~{result.pipeline.total_words_to_llm}</strong> kelime</span>
                </div>
              </div>

              {/* Accepted Sub-chunks */}
              <div className="bg-white rounded-xl border border-[#e2e8e5] overflow-hidden">
                <div className="px-4 py-3 bg-emerald-50 border-b border-emerald-100 flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-emerald-600" />
                  <h3 className="text-[13px] font-semibold text-emerald-800">
                    LLM'e Gönderilen Alt-Parçalar ({result.final_sub_chunks.length})
                  </h3>
                </div>
                <div className="divide-y divide-[#e2e8e5]">
                  {result.final_sub_chunks.map((chunk, i) => (
                    <div key={i} className="px-4 py-3 hover:bg-[#f8faf9] transition-colors">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] font-mono text-white bg-[#047857] w-5 h-5 rounded flex items-center justify-center">
                          {chunk.rank}
                        </span>
                        <span className="text-[12px] font-medium text-[#1a2e28]">{chunk.source}</span>
                        <span className="text-[10px] text-[#9aada2]">{chunk.word_count} kelime</span>
                        <div className="ml-auto flex items-center gap-2">
                          <ScoreBadge score={chunk.ce_score} label="CE" />
                          {chunk.similarity != null && <ScoreBadge score={chunk.similarity} label="Sim" />}
                        </div>
                      </div>
                      <p className="text-[12px] text-[#5f7068] leading-relaxed bg-[#f8faf9] rounded-lg p-2.5 border border-[#e2e8e5]">
                        {chunk.text}
                      </p>
                    </div>
                  ))}
                  {result.final_sub_chunks.length === 0 && (
                    <div className="px-4 py-8 text-center text-[13px] text-[#9aada2]">
                      Eşik değerini geçen alt-parça bulunamadı
                    </div>
                  )}
                </div>
              </div>

              {/* Rejected Sub-chunks */}
              {result.rejected_sub_chunks.length > 0 && (
                <div className="bg-white rounded-xl border border-[#e2e8e5] overflow-hidden">
                  <button
                    onClick={() => setShowRejected(!showRejected)}
                    className="w-full px-4 py-3 bg-red-50 border-b border-red-100 flex items-center gap-2 hover:bg-red-100/50 transition-colors"
                  >
                    <XCircle className="h-4 w-4 text-red-500" />
                    <h3 className="text-[13px] font-semibold text-red-800">
                      Elenen Alt-Parçalar ({result.pipeline.rejected_by_threshold})
                    </h3>
                    <span className="text-[11px] text-red-400 ml-1">CE &lt; {result.pipeline.threshold}</span>
                    <div className="ml-auto">
                      {showRejected ? <ChevronUp className="h-4 w-4 text-red-400" /> : <ChevronDown className="h-4 w-4 text-red-400" />}
                    </div>
                  </button>
                  {showRejected && (
                    <div className="divide-y divide-[#e2e8e5]">
                      {result.rejected_sub_chunks.map((chunk, i) => (
                        <div key={i} className="px-4 py-2.5 opacity-60">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-[12px] text-[#5f7068]">{chunk.source}</span>
                            <ScoreBadge score={chunk.ce_score} label="CE" />
                          </div>
                          <p className="text-[11px] text-[#9aada2] line-clamp-1">{chunk.text}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
