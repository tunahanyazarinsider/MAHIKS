import { useState } from 'react';
import { User, HeartPulse, FileText, ChevronDown, ChevronUp, Search, Zap, Clock } from 'lucide-react';
import { Message } from '../models';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.sender === 'user';
  const [showCitations, setShowCitations] = useState(false);
  const [showRagDetails, setShowRagDetails] = useState(false);

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
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Action buttons row */}
        {!isUser && !message.isLoading && (message.citations?.length || message.ragMetadata) && (
          <div className="flex items-center gap-3">
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
          </div>
        )}

        {/* Citations panel */}
        {showCitations && message.citations && message.citations.length > 0 && (
          <div className="w-full px-3 py-2.5 bg-[#f8faf9] rounded-lg border border-[#e2e8e5] space-y-1.5">
            {message.citations.map((citation, i) => (
              <div key={i} className="flex items-center gap-2 text-[12px]">
                <div className="w-5 h-5 rounded bg-[#ecfdf5] flex items-center justify-center shrink-0">
                  <FileText className="h-3 w-3 text-[#047857]" />
                </div>
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
            ))}
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
          </div>
        )}

        <span className="text-[11px] text-[#9aada2] px-1 tabular-nums">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}
