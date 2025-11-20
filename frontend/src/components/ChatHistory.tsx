import { ScrollArea } from './ui/scroll-area';
import { Button } from './ui/button';
import { MessageSquarePlus, MessageSquare, Trash2, Pencil } from 'lucide-react';
import { Separator } from './ui/separator';

export interface Conversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  messageCount: number;
}

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
  const formatDate = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
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
    <div className="w-80 bg-white border-r flex flex-col h-full">
      <div className="p-4 border-b">
        <Button onClick={onNewConversation} className="w-full">
          <MessageSquarePlus className="h-4 w-4 mr-2" />
          New Conversation
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2">
          {Object.entries(groupedConversations).map(([date, convs]) => (
            <div key={date} className="mb-4">
              <div className="px-3 py-2 text-xs text-gray-500">{date}</div>
              <div className="space-y-1">
                {convs.map((conversation) => (
                  <div
                    key={conversation.id}
                    className={`group relative rounded-lg p-3 cursor-pointer transition-colors ${
                      currentConversationId === conversation.id
                        ? 'bg-blue-50 border border-blue-200'
                        : 'hover:bg-gray-50'
                    }`}
                    onClick={() => onSelectConversation(conversation.id)}
                  >
                    <div className="flex items-start gap-2">
                      <MessageSquare className="h-4 w-4 text-gray-400 flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm truncate">{conversation.title}</p>
                        <p className="text-xs text-gray-500 truncate mt-1">
                          {conversation.lastMessage}
                        </p>
                        <p className="text-xs text-gray-400 mt-1">
                          {conversation.messageCount} messages
                        </p>
                      </div>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity absolute top-2 right-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            onRenameConversation(conversation.id);
                          }}
                        >
                          <Pencil className="h-3 w-3 text-gray-400 hover:text-blue-500" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteConversation(conversation.id);
                          }}
                        >
                          <Trash2 className="h-3 w-3 text-gray-400 hover:text-red-500" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {conversations.length === 0 && (
            <div className="text-center py-8 px-4">
              <MessageSquare className="h-12 w-12 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No conversations yet</p>
              <p className="text-xs text-gray-400 mt-1">Start a new conversation to begin</p>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
