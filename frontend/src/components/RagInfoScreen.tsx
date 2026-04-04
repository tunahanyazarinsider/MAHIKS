import { ArrowLeft, FileText, Search, Layers, Brain, SlidersHorizontal, MessageSquare } from 'lucide-react';

interface RagInfoScreenProps {
  onBack: () => void;
}

const PIPELINE_STEPS = [
  {
    icon: FileText,
    title: 'Belge Yükleme',
    desc: 'PDF belgeler sisteme yüklenir, metin çıkarılır ve 500 kelimelik parçalara bölünür.',
    detail: 'Chunk Size: 500 kelime, Overlap: 50 kelime',
    color: 'bg-blue-50 text-blue-600',
  },
  {
    icon: Layers,
    title: 'Vektör Oluşturma (BGE-M3)',
    desc: 'Her parça, BAAI/bge-m3 modeli ile 1024 boyutlu vektöre dönüştürülür ve ChromaDB\'ye kaydedilir.',
    detail: 'Model: BAAI/bge-m3 | Boyut: 1024d | DB: ChromaDB',
    color: 'bg-purple-50 text-purple-600',
  },
  {
    icon: Search,
    title: 'Hibrit Arama',
    desc: 'Sorgunuz hem vektör benzerliği (semantik) hem de BM25 (anahtar kelime) ile aranır. Sonuçlar RRF ile birleştirilir.',
    detail: 'Vektör Top-10 + BM25 Top-10 → RRF Fusion',
    color: 'bg-amber-50 text-amber-600',
  },
  {
    icon: SlidersHorizontal,
    title: 'Alt-Parça Reranking',
    desc: 'Büyük parçalar ~120 kelimelik alt-parçalara bölünür. Cross-encoder modeli her alt-parçayı sorguya göre puanlar.',
    detail: '10 parça → ~60 alt-parça → Top 10 (mmarco-mMiniLMv2)',
    color: 'bg-rose-50 text-rose-600',
  },
  {
    icon: Brain,
    title: 'LLM Yanıt Üretimi',
    desc: 'En alakalı alt-parçalar (~1200 kelime) Qwen 2.5 modeline gönderilir ve Türkçe yanıt üretilir.',
    detail: 'Model: Qwen 2.5 (7B) | Ollama | ~42 tok/s',
    color: 'bg-emerald-50 text-emerald-600',
  },
  {
    icon: MessageSquare,
    title: 'Kaynak Gösterimi',
    desc: 'Yanıt, kullanılan kaynaklar ve güvenilirlik puanları ile birlikte sunulur.',
    detail: 'Similarity + Cross-Encoder skorları',
    color: 'bg-teal-50 text-teal-600',
  },
];

export function RagInfoScreen({ onBack }: RagInfoScreenProps) {
  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#f8faf9]">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-[#e2e8e5] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3 max-w-[900px] mx-auto w-full">
          <button
            onClick={onBack}
            className="p-2 rounded-lg hover:bg-[#f1f5f3] transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-[#5f7068]" />
          </button>
          <div>
            <h1 className="text-[15px] font-semibold text-[#1a2e28]" style={{ fontFamily: 'var(--font-serif)' }}>
              RAG Pipeline
            </h1>
            <p className="text-[11px] text-[#9aada2]">Retrieval-Augmented Generation</p>
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[700px] mx-auto px-6 py-8">
          {/* Intro */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-[#1a2e28] mb-2" style={{ fontFamily: 'var(--font-serif)' }}>
              Sistem Nasıl Çalışır?
            </h2>
            <p className="text-[14px] text-[#5f7068] leading-relaxed">
              Sorularınız doğrudan yapay zekaya gitmez. Önce belgelerinizde en alakalı bölümler bulunur,
              sonra bu bölümler bağlam olarak LLM'e gönderilir. Bu sayede yanıtlar belgelere dayalı ve doğrulanabilir olur.
            </p>
          </div>

          {/* Pipeline steps */}
          <div className="space-y-4">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={i} className="flex gap-4">
                {/* Timeline */}
                <div className="flex flex-col items-center shrink-0">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${step.color}`}>
                    <step.icon className="w-5 h-5" />
                  </div>
                  {i < PIPELINE_STEPS.length - 1 && (
                    <div className="w-px h-full min-h-[20px] bg-[#d4ddd8] my-1" />
                  )}
                </div>

                {/* Content */}
                <div className="pb-4">
                  <h3 className="text-[14px] font-semibold text-[#1a2e28] mb-1">
                    {step.title}
                  </h3>
                  <p className="text-[13px] text-[#5f7068] leading-relaxed mb-2">
                    {step.desc}
                  </p>
                  <div className="inline-block text-[11px] font-mono text-[#9aada2] bg-[#f1f5f3] px-2.5 py-1 rounded-md">
                    {step.detail}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Architecture diagram (text) */}
          <div className="mt-8 p-4 bg-white rounded-xl border border-[#e2e8e5]">
            <h3 className="text-[13px] font-semibold text-[#1a2e28] mb-3">Veri Akışı</h3>
            <pre className="text-[11px] font-mono text-[#5f7068] leading-relaxed overflow-x-auto whitespace-pre">
{`Sorgu
  │
  ├─→ Vektör Arama (ChromaDB / BGE-M3)  ──→ 10 sonuç ─┐
  │                                                      ├─→ RRF Fusion
  └─→ BM25 Arama (Anahtar Kelime)       ──→ 10 sonuç ─┘
                                                          │
                                                    Top 10 parça
                                                          │
                                                  Alt-parçalara böl
                                                   (~120 kelime × ~60)
                                                          │
                                                   Cross-Encoder
                                                    Reranking
                                                          │
                                                  Top 10 alt-parça
                                                  (~1200 kelime)
                                                          │
                                                    Qwen 2.5 (7B)
                                                          │
                                                       Yanıt`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
