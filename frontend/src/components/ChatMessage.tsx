import { useState, useRef, useEffect, useMemo } from 'react';
import { User, HeartPulse, FileText, ChevronDown, ChevronUp, Search, Zap, Clock, ThumbsUp, ThumbsDown, AlertTriangle } from 'lucide-react';
import { Message } from '../models';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { KgPathBadge } from './KgPathBadge';

interface ChatMessageProps {
  message: Message;
  onFeedback?: (rating: 'up' | 'down', reason?: string) => Promise<void>;
}

const CITE_TOKEN_RE = /__CITE_(\d+)__/;

// Swap [N] markers for an inline-code token so ReactMarkdown delivers them
// to our `code` renderer as a single atomic unit. We rebuild as `\`__CITE_N__\``.
function injectCitationMarkers(text: string): string {
  return text.replace(/\[(\d+)\]/g, '`__CITE_$1__`');
}

export function ChatMessage({ message, onFeedback }: ChatMessageProps) {
  const isUser = message.sender === 'user';
  const [showCitations, setShowCitations] = useState(false);
  const [showRagDetails, setShowRagDetails] = useState(false);
  const [showReasonForm, setShowReasonForm] = useState(false);
  const [reasonText, setReasonText] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const citationRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const feedback = message.feedback ?? null;
  // Feedback can only be POSTed once the agent message has a backend row.
  // Until then, thumbs are visible but disabled so the affordance stays present.
  const canSubmitFeedback = !!message.backendId;

  const handleThumbUp = async () => {
    if (!onFeedback || !canSubmitFeedback || submittingFeedback) return;
    setSubmittingFeedback(true);
    try {
      await onFeedback('up');
      setShowReasonForm(false);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const handleThumbDownClick = () => {
    if (!onFeedback || !canSubmitFeedback || submittingFeedback) return;
    setShowReasonForm(true);
  };

  const handleSubmitReason = async (skipReason = false) => {
    if (!onFeedback || submittingFeedback) return;
    setSubmittingFeedback(true);
    try {
      await onFeedback('down', skipReason ? undefined : reasonText.trim() || undefined);
      setShowReasonForm(false);
      setReasonText('');
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const hasInlineCitations = useMemo(
    () => !isUser && /\[(\d+)\]/.test(message.content || ''),
    [isUser, message.content],
  );

  // Auto-expand citation panel the first time the answer references [N].
  useEffect(() => {
    if (hasInlineCitations) setShowCitations(true);
  }, [hasInlineCitations]);

  const focusCitation = (n: number) => {
    setShowCitations(true);
    requestAnimationFrame(() => {
      const el = citationRefs.current[n];
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.animate(
        [{ backgroundColor: '#a7f3d0' }, { backgroundColor: 'transparent' }],
        { duration: 1400, easing: 'ease-out' },
      );
    });
  };

  const formatTime = (date: Date): string => {
    return date.toLocaleTimeString('tr-TR', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatScore = (score: number): string => {
    return (score * 100).toFixed(1);
  };

  const getScoreColor = (score: number): string => {
    if (score >= 0.8) return 'text-emerald-600 bg-emerald-50';
    if (score >= 0.5) return 'text-amber-600 bg-amber-50';
    return 'text-gray-500 bg-gray-100';
  };

  return (
    <div
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
      role="article"
      aria-label={isUser ? 'Sizin mesajınız' : 'Asistan yanıtı'}
      data-testid={isUser ? 'user-message' : 'agent-message'}
      data-message-id={message.backendId ?? ''}
      data-loading={message.isLoading ? 'true' : 'false'}
    >
      {/* Avatar */}
      <div
        className={`h-8 w-8 rounded-full flex items-center justify-center shrink-0 shadow-sm ${
          isUser
            ? 'bg-[#1a2e28]'
            : 'bg-gradient-to-br from-[#047857] to-[#065f46]'
        }`}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5 text-white" />
        ) : (
          <HeartPulse className="h-3.5 w-3.5 text-white" />
        )}
      </div>

      {/* Message Content */}
      <div className={`flex flex-col gap-1 max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Low-confidence banner — rendered above the bubble so the user
            sees the caveat before reading the answer. */}
        {!isUser && message.confidence?.level === 'low' && (
          <div className="flex items-start gap-2 px-3 py-2 rounded-lg border border-amber-200 bg-amber-50 text-[12px] text-amber-900 max-w-full">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 mt-0.5 shrink-0" />
            <div className="leading-snug">
              <span className="font-medium">Düşük kaynak güveni.</span>{' '}
              Bu yanıtı SGK ALO 170 veya resmi SUT belgesinden doğrulayın.
            </div>
          </div>
        )}
        <div
          className={`rounded-2xl px-4 py-2.5 ${
            isUser
              ? 'bg-[#1a2e28] text-white rounded-br-md'
              : 'bg-white text-[#1a2e28] border border-[#e2e8e5] shadow-sm rounded-bl-md'
          }`}
        >
          {message.isLoading ? (
            <div className="flex items-center gap-1.5 py-1 px-1">
              <span className="w-2 h-2 bg-[#9aada2] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-[#9aada2] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-[#9aada2] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          ) : isUser ? (
            <p className="whitespace-pre-wrap break-words text-[0.9375rem] leading-relaxed">{message.content}</p>
          ) : (
            <div className="chat-markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ children, className, ...props }) {
                    const raw = Array.isArray(children) ? children.join('') : String(children ?? '');
                    const m = raw.match(CITE_TOKEN_RE);
                    if (m) {
                      const n = parseInt(m[1], 10);
                      return (
                        <button
                          type="button"
                          onClick={() => focusCitation(n)}
                          className="inline-flex items-center justify-center min-w-[20px] h-[18px] px-1 mx-0.5 text-[10px] font-mono rounded bg-[#ecfdf5] text-[#047857] border border-[#a7f3d0] hover:bg-[#047857] hover:text-white transition-colors align-middle"
                          aria-label={`Kaynak ${n}`}
                        >
                          {n}
                        </button>
                      );
                    }
                    return <code className={className} {...props}>{children}</code>;
                  },
                }}
              >
                {injectCitationMarkers(message.content)}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Action buttons row */}
        {!isUser && !message.isLoading && (message.citations?.length || message.ragMetadata || onFeedback) && (
          <div className="flex items-center gap-3 flex-wrap">
            {/* Citations toggle */}
            {message.citations && message.citations.length > 0 && (
              <button
                onClick={() => setShowCitations(!showCitations)}
                className="inline-flex items-center gap-1.5 text-[11px] text-[#5f7068] hover:text-[#047857] px-1 py-1 transition-colors"
              >
                <FileText className="h-3 w-3" />
                <span className="font-medium">{message.citations.length} kaynak</span>
                {showCitations ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
            )}

            {/* RAG details toggle */}
            {message.ragMetadata && (
              <button
                onClick={() => setShowRagDetails(!showRagDetails)}
                className="inline-flex items-center gap-1.5 text-[11px] text-[#5f7068] hover:text-[#047857] px-1 py-1 transition-colors"
              >
                <Search className="h-3 w-3" />
                <span className="font-medium">RAG detay</span>
                {showRagDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
            )}

            {/* Feedback thumbs */}
            {onFeedback && (
              <div className="inline-flex items-center gap-1 ml-auto">
                <button
                  onClick={handleThumbUp}
                  disabled={!canSubmitFeedback || submittingFeedback}
                  aria-label="Bu yanıtı beğen"
                  aria-pressed={feedback === 'up'}
                  className={`p-1 rounded transition-colors disabled:opacity-50 ${
                    feedback === 'up'
                      ? 'text-[#047857] bg-[#ecfdf5]'
                      : 'text-[#9aada2] hover:text-[#047857] hover:bg-[#f1f5f3]'
                  }`}
                >
                  <ThumbsUp className="h-3.5 w-3.5" fill={feedback === 'up' ? 'currentColor' : 'none'} />
                </button>
                <button
                  onClick={handleThumbDownClick}
                  disabled={!canSubmitFeedback || submittingFeedback}
                  aria-label="Bu yanıtı beğenme"
                  aria-pressed={feedback === 'down'}
                  className={`p-1 rounded transition-colors disabled:opacity-50 ${
                    feedback === 'down'
                      ? 'text-red-600 bg-red-50'
                      : 'text-[#9aada2] hover:text-red-600 hover:bg-red-50'
                  }`}
                >
                  <ThumbsDown className="h-3.5 w-3.5" fill={feedback === 'down' ? 'currentColor' : 'none'} />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Down-vote reason form */}
        {showReasonForm && onFeedback && (
          <div className="w-full px-3 py-2.5 bg-red-50/50 rounded-lg border border-red-100 space-y-2">
            <label className="text-[11px] text-[#5f7068] block">
              Neden beğenmediniz? (isteğe bağlı)
            </label>
            <textarea
              value={reasonText}
              onChange={(e) => setReasonText(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="Örn. kaynak eksik, yanlış bilgi…"
              className="w-full px-2 py-1.5 text-[12px] rounded border border-[#e2e8e5] focus:border-red-300 focus:ring-1 focus:ring-red-100 outline-none resize-none bg-white"
              disabled={submittingFeedback}
            />
            <div className="flex items-center gap-2 justify-end">
              <button
                onClick={() => { setShowReasonForm(false); setReasonText(''); }}
                disabled={submittingFeedback}
                className="text-[11px] text-[#5f7068] hover:text-[#1a2e28] px-2 py-1 transition-colors disabled:opacity-50"
              >
                Vazgeç
              </button>
              <button
                onClick={() => handleSubmitReason(true)}
                disabled={submittingFeedback}
                className="text-[11px] text-[#5f7068] hover:text-red-700 px-2 py-1 transition-colors disabled:opacity-50"
              >
                Sebep yazmadan gönder
              </button>
              <button
                onClick={() => handleSubmitReason(false)}
                disabled={submittingFeedback}
                className="text-[11px] font-medium text-white bg-red-600 hover:bg-red-700 px-3 py-1 rounded transition-colors disabled:opacity-50"
              >
                Gönder
              </button>
            </div>
          </div>
        )}

        {/* Citations panel */}
        {showCitations && message.citations && message.citations.length > 0 && (
          <div className="w-full px-3 py-2.5 bg-[#f8faf9] rounded-lg border border-[#e2e8e5] space-y-1.5">
            {message.citations.map((citation, i) => {
              const idx = citation.index ?? i + 1;
              return (
                <div
                  key={idx}
                  ref={(el) => { citationRefs.current[idx] = el; }}
                  className="flex items-start gap-2 text-[12px] rounded px-1 py-0.5"
                >
                  <span
                    className="w-5 h-[18px] mt-0.5 rounded font-mono text-[10px] bg-[#ecfdf5] text-[#047857] border border-[#a7f3d0] flex items-center justify-center shrink-0"
                    aria-hidden="true"
                  >
                    {idx}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1 truncate">
                      <FileText className="h-3 w-3 text-[#047857] shrink-0" />
                      <span className="truncate text-[#1a2e28] font-medium">
                        {citation.source}
                        {citation.section_number && (
                          <span className="text-[#5f7068] font-normal"> · §{citation.section_number}</span>
                        )}
                        {citation.section_title && (
                          <span className="text-[#5f7068] font-normal"> — {citation.section_title}</span>
                        )}
                      </span>
                      {citation.relevance_score != null && (
                        <span className="ml-auto text-[11px] text-[#9aada2] tabular-nums shrink-0">
                          {(citation.relevance_score * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    {citation.content && (
                      <p className="mt-1 text-[11px] text-[#5f7068] leading-relaxed line-clamp-2">
                        {citation.content}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* RAG Details panel */}
        {showRagDetails && message.ragMetadata && (
          <div className="w-full rounded-lg border border-[#d4ddd8] overflow-hidden">
            {/* RAG header stats */}
            <div className="bg-[#f1f5f3] px-3 py-2 flex items-center gap-4 text-[11px] text-[#5f7068]">
              <div className="flex items-center gap-1">
                <Search className="h-3 w-3" />
                <span>{message.ragMetadata.chunks_retrieved} parça</span>
              </div>
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                <span>{message.ragMetadata.retrieval_time_ms}ms</span>
              </div>
              <div className="flex items-center gap-1">
                <Zap className="h-3 w-3" />
                <span>{message.ragMetadata.model}</span>
              </div>
            </div>

            {/* Sub-chunks list */}
            <div className="divide-y divide-[#e2e8e5]">
              {message.ragMetadata.sub_chunks.map((chunk, i) => (
                <div key={i} className="px-3 py-2 bg-white hover:bg-[#f8faf9] transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-mono text-[#9aada2]">#{i + 1}</span>
                    <span className="text-[11px] font-medium text-[#1a2e28] truncate">{chunk.source}</span>
                    <div className="ml-auto flex items-center gap-2 shrink-0">
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${getScoreColor(chunk.ce_score)}`}>
                        CE: {formatScore(chunk.ce_score)}%
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-50 text-gray-500">
                        Sim: {formatScore(chunk.similarity)}%
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] text-[#5f7068] leading-relaxed line-clamp-2">
                    {chunk.text}
                  </p>
                </div>
              ))}
            </div>

            {/* Knowledge-graph facts the answer was conditioned on */}
            {message.graphFacts && message.graphFacts.length > 0 && (
              <div className="border-t border-[#e2e8e5] bg-[#f8faf9] px-3 py-2.5">
                <div className="text-[10px] uppercase tracking-wider text-[#9aada2] mb-1.5">
                  Bilgi grafiği bağlantıları
                </div>
                <div className="space-y-1">
                  {message.graphFacts.map((fact, i) => (
                    <KgPathBadge key={i} fact={fact} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <span className="text-[11px] text-[#9aada2] px-1 tabular-nums">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}
