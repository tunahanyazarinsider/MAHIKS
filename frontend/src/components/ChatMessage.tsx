import { useState } from 'react';
import { User, HeartPulse, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { Message } from '../models';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.sender === 'user';
  const [showCitations, setShowCitations] = useState(false);

  const formatTime = (date: Date): string => {
    return date.toLocaleTimeString('tr-TR', {
      hour: '2-digit',
      minute: '2-digit'
    });
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

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="w-full">
            <button
              onClick={() => setShowCitations(!showCitations)}
              className="inline-flex items-center gap-1.5 text-[11px] text-[#5f7068] hover:text-[#047857] px-1 py-1 transition-colors"
            >
              <FileText className="h-3 w-3" />
              <span className="font-medium">{message.citations.length} kaynak</span>
              {showCitations ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>
            {showCitations && (
              <div className="mt-1 px-3 py-2.5 bg-[#f8faf9] rounded-lg border border-[#e2e8e5] space-y-1.5">
                {message.citations.map((citation, i) => (
                  <div key={i} className="flex items-center gap-2 text-[12px]">
                    <div className="w-5 h-5 rounded bg-[#ecfdf5] flex items-center justify-center shrink-0">
                      <FileText className="h-3 w-3 text-[#047857]" />
                    </div>
                    <span className="truncate text-[#1a2e28] font-medium">{citation.source}</span>
                    {citation.relevance_score != null && (
                      <span className="ml-auto text-[11px] text-[#9aada2] tabular-nums shrink-0">
                        {(citation.relevance_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                ))}
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
