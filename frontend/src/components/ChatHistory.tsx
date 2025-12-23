import { useState } from 'react';
import { Button } from './ui/button';
import { MessageSquarePlus, MessageSquare, Trash2, Pencil } from 'lucide-react';
import { DeleteDialog } from './DeleteDialog';
import { Conversation } from '../models';

interface ChatHistoryProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string) => void;
}

export function ChatHistory({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation
}: ChatHistoryProps) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null);
  
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

  const handleDeleteClick = (e: React.MouseEvent, conversationId: string) => {
    e.stopPropagation();
    setDeletingConversationId(conversationId);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (deletingConversationId) {
      onDeleteConversation(deletingConversationId);
      setDeletingConversationId(null);
    }
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
    <>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        {/* New Chat Button */}
        <div style={{ padding: '16px', borderBottom: '1px solid #e5e7eb', flexShrink: 0 }}>
          <Button onClick={onNewConversation} className="w-full">
            <MessageSquarePlus className="h-4 w-4 mr-2" />
            Yeni Sohbet
          </Button>
        </div>

        {/* Chat List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
          {Object.entries(groupedConversations).map(([date, convs]) => (
            <div key={date} style={{ marginBottom: '16px' }}>
              <div style={{ padding: '8px 12px', fontSize: '12px', fontWeight: 500, color: '#6b7280', textTransform: 'uppercase' }}>
                {date}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {convs.map((conversation) => (
                  <div
                    key={conversation.id}
                    onClick={() => onSelectConversation(conversation.id)}
                    style={{
                      padding: '12px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      backgroundColor: currentConversationId === conversation.id ? '#eff6ff' : 'transparent',
                      border: currentConversationId === conversation.id ? '1px solid #bfdbfe' : '1px solid transparent',
                      position: 'relative'
                    }}
                    className="group hover:bg-gray-50"
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <MessageSquare style={{ width: '16px', height: '16px', color: '#9ca3af', flexShrink: 0, marginTop: '2px' }} />
                      <div style={{ overflow: 'hidden', flex: 1, minWidth: 0 }}>
                        <p style={{ 
                          fontSize: '14px', 
                          fontWeight: 500, 
                          whiteSpace: 'nowrap', 
                          overflow: 'hidden', 
                          textOverflow: 'ellipsis',
                          color: '#111827'
                        }}>
                          {conversation.title}
                        </p>
                        <p style={{ 
                          fontSize: '12px', 
                          color: '#6b7280', 
                          marginTop: '4px',
                          whiteSpace: 'nowrap', 
                          overflow: 'hidden', 
                          textOverflow: 'ellipsis'
                        }}>
                          {conversation.lastMessage}
                        </p>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '4px' }}>
                          {formatMessageCount(conversation.messageCount)}
                        </p>
                      </div>
                    </div>
                    
                    {/* Action Buttons */}
                    <div 
                      className="opacity-0 group-hover:opacity-100"
                      style={{ 
                        position: 'absolute', 
                        top: '8px', 
                        right: '8px', 
                        display: 'flex', 
                        gap: '4px',
                        transition: 'opacity 0.2s'
                      }}
                    >
                      <Button
                        variant="ghost"
                        size="sm"
                        style={{ height: '28px', width: '28px', padding: 0 }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onRenameConversation(conversation.id);
                        }}
                      >
                        <Pencil style={{ width: '12px', height: '12px', color: '#9ca3af' }} />
                      </Button>

                      <Button
                        variant="ghost"
                        size="sm"
                        style={{ height: '28px', width: '28px', padding: 0 }}
                        onClick={(e) => handleDeleteClick(e, conversation.id)}
                      >
                        <Trash2 style={{ width: '12px', height: '12px', color: '#9ca3af' }} />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* Empty State */}
          {conversations.length === 0 && (
            <div style={{ textAlign: 'center', padding: '48px 16px' }}>
              <div style={{ 
                backgroundColor: '#f3f4f6', 
                borderRadius: '50%', 
                width: '64px', 
                height: '64px', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center', 
                margin: '0 auto 16px' 
              }}>
                <MessageSquare style={{ width: '32px', height: '32px', color: '#9ca3af' }} />
              </div>
              <p style={{ fontSize: '14px', fontWeight: 500, color: '#4b5563' }}>Henüz sohbet yok</p>
              <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '8px' }}>
                Sağlık sigortası hakkında soru sormak için yukarıdaki butona tıklayın
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <DeleteDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
      />
    </>
  );
}