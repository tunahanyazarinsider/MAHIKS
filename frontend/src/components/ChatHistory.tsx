import { Button } from './ui/button';
import { MessageSquarePlus, MessageSquare, Trash2, Pencil, BrainCircuit, FlaskConical } from 'lucide-react';
import { Conversation } from '../models';

interface ChatHistoryProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string) => void;
  onShowRagInfo?: () => void;
  onShowEvalDashboard?: () => void;
}

export function ChatHistory({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  onShowRagInfo,
  onShowEvalDashboard,
}: ChatHistoryProps) {

  const formatDate = (date: Date): string => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return 'Bugün';
    if (days === 1) return 'Dün';
    if (days < 7) return `${days} gün önce`;
    if (days < 30) return `${Math.floor(days / 7)} hafta önce`;

    return date.toLocaleDateString('tr-TR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  const formatMessageCount = (count: number): string => {
    if (count === 0) return 'Mesaj yok';
    if (count === 1) return '1 mesaj';
    return `${count} mesaj`;
  };

  const groupedConversations = conversations.reduce((groups, conv) => {
    const date = formatDate(conv.timestamp);
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(conv);
    return groups;
  }, {} as Record<string, Conversation[]>);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* New Chat Button */}
      <div className="p-4 border-b border-[#e2e8e5] shrink-0">
        <Button
          onClick={onNewConversation}
          className="w-full bg-[#047857] hover:bg-[#065f46] text-white"
        >
          <MessageSquarePlus className="h-4 w-4 mr-2" />
          Yeni Sohbet
        </Button>
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {Object.entries(groupedConversations).map(([date, convs]) => (
          <div key={date} className="mb-4">
            <div className="px-3 py-1.5 text-[11px] font-semibold text-[#5f7068] uppercase tracking-wider">
              {date}
            </div>
            <div className="flex flex-col gap-0.5">
              {convs.map((conversation) => {
                const isActive = currentConversationId === conversation.id;
                return (
                  <div
                    key={conversation.id}
                    onClick={() => onSelectConversation(conversation.id)}
                    className={`
                      group relative px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-150
                      ${isActive
                        ? 'bg-[#ecfdf5] border border-[#a7f3d0] shadow-sm'
                        : 'border border-transparent hover:bg-[#f1f5f3]'
                      }
                    `}
                  >
                    <div className="flex items-start gap-2.5">
                      <MessageSquare className={`w-4 h-4 mt-0.5 shrink-0 ${isActive ? 'text-[#047857]' : 'text-[#9aada2]'}`} />

                      <div className="flex-1 min-w-0">
                        <p className={`text-[13px] font-medium truncate ${isActive ? 'text-[#047857]' : 'text-[#1a2e28]'}`}>
                          {conversation.title}
                        </p>
                        <p className="text-[12px] text-[#5f7068] mt-0.5 truncate">
                          {conversation.lastMessage}
                        </p>
                        <p className="text-[11px] text-[#9aada2] mt-1">
                          {formatMessageCount(conversation.messageCount)}
                        </p>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        <button
                          className="p-1 rounded hover:bg-[#d4ddd8]/50 transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            onRenameConversation(conversation.id);
                          }}
                          aria-label="Yeniden adlandır"
                        >
                          <Pencil className="w-3 h-3 text-[#5f7068]" />
                        </button>
                        <button
                          className="p-1 rounded hover:bg-red-50 transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteConversation(conversation.id);
                          }}
                          aria-label="Sil"
                        >
                          <Trash2 className="w-3 h-3 text-[#5f7068] hover:text-red-500" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {/* Empty State */}
        {conversations.length === 0 && (
          <div className="text-center py-12 px-4">
            <div className="w-14 h-14 bg-[#ecfdf5] rounded-full flex items-center justify-center mx-auto mb-4">
              <MessageSquare className="w-6 h-6 text-[#047857]" />
            </div>
            <p className="text-sm font-medium text-[#1a2e28]">Henüz sohbet yok</p>
            <p className="text-xs text-[#9aada2] mt-2 leading-relaxed">
              Sağlık sigortası hakkında soru sormak için yukarıdaki butona tıklayın
            </p>
          </div>
        )}
      </div>

      {/* Sidebar tool buttons */}
      {(onShowRagInfo || onShowEvalDashboard) && (
        <div className="p-3 border-t border-[#e2e8e5] shrink-0 space-y-2">
          {onShowRagInfo && (
            <button
              onClick={onShowRagInfo}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-[#f1f5f3] hover:bg-[#ecfdf5] border border-[#e2e8e5] hover:border-[#a7f3d0] transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-[#ecfdf5] group-hover:bg-[#d1fae5] flex items-center justify-center shrink-0 transition-colors">
                <BrainCircuit className="w-4 h-4 text-[#047857]" />
              </div>
              <div className="text-left">
                <p className="text-[12px] font-semibold text-[#1a2e28]">RAG Pipeline</p>
                <p className="text-[10px] text-[#9aada2]">Sistem nasıl çalışır?</p>
              </div>
            </button>
          )}
          {onShowEvalDashboard && (
            <button
              onClick={onShowEvalDashboard}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-[#f1f5f3] hover:bg-[#ecfdf5] border border-[#e2e8e5] hover:border-[#a7f3d0] transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-[#ecfdf5] group-hover:bg-[#d1fae5] flex items-center justify-center shrink-0 transition-colors">
                <FlaskConical className="w-4 h-4 text-[#047857]" />
              </div>
              <div className="text-left">
                <p className="text-[12px] font-semibold text-[#1a2e28]">Değerlendirme</p>
                <p className="text-[10px] text-[#9aada2]">Eval metrikleri ve eğilim</p>
              </div>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
