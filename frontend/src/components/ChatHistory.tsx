import { ScrollArea } from './ui/scroll-area';
import { Button } from './ui/button';
import { MessageSquarePlus, MessageSquare, Trash2, Pencil } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './ui/tooltip';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from './ui/alert-dialog';
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
  
  // Format date in Turkish locale
  const formatDate = (date: Date): string => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return 'Bugün';
    if (days === 1) return 'Dün';
    if (days < 7) return `${days} gün önce`;
    if (days < 30) return `${Math.floor(days / 7)} hafta önce`;
    
    // Turkish date format: 15 Ocak 2024
    return date.toLocaleDateString('tr-TR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  // Format message count with correct Turkish grammar
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
    <TooltipProvider>
      <div className="w-80 bg-white border-r flex flex-col h-full">
        {/* New Chat Button */}
        <div className="p-4 border-b">
          <Button 
            onClick={onNewConversation} 
            className="w-full"
            aria-label="Yeni sohbet başlat"
          >
            <MessageSquarePlus className="h-4 w-4 mr-2" />
            Yeni Sohbet
          </Button>
        </div>

        {/* Chat List */}
        <ScrollArea className="flex-1">
          <div className="p-2">
            {Object.entries(groupedConversations).map(([date, convs]) => (
              <div key={date} className="mb-4">
                <div className="px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  {date}
                </div>
                <div className="space-y-1">
                  {convs.map((conversation) => (
                    <div
                      key={conversation.id}
                      role="button"
                      tabIndex={0}
                      aria-selected={currentConversationId === conversation.id}
                      aria-label={`${conversation.title} - ${formatMessageCount(conversation.messageCount)}`}
                      className={`group relative rounded-lg p-3 cursor-pointer transition-colors ${
                        currentConversationId === conversation.id
                          ? 'bg-blue-50 border border-blue-200'
                          : 'hover:bg-gray-50'
                      }`}
                      onClick={() => onSelectConversation(conversation.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onSelectConversation(conversation.id);
                        }
                      }}
                    >
                      <div className="flex items-start gap-2">
                        <MessageSquare className="h-4 w-4 text-gray-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0 pr-16">
                          <p className="text-sm font-medium truncate">
                            {conversation.title}
                          </p>
                          <p className="text-xs text-gray-500 truncate mt-1">
                            {conversation.lastMessage}
                          </p>
                          <p className="text-xs text-gray-400 mt-1">
                            {formatMessageCount(conversation.messageCount)}
                          </p>
                        </div>
                        
                        {/* Action Buttons */}
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity absolute top-2 right-2">
                          {/* Rename Button */}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0"
                                aria-label="Sohbeti yeniden adlandır"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onRenameConversation(conversation.id);
                                }}
                              >
                                <Pencil className="h-3 w-3 text-gray-400 hover:text-blue-500" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Yeniden Adlandır</p>
                            </TooltipContent>
                          </Tooltip>

                          {/* Delete Button with Confirmation */}
                          <AlertDialog>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <AlertDialogTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 w-8 p-0"
                                    aria-label="Sohbeti sil"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <Trash2 className="h-3 w-3 text-gray-400 hover:text-red-500" />
                                  </Button>
                                </AlertDialogTrigger>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Sil</p>
                              </TooltipContent>
                            </Tooltip>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Sohbeti Sil</AlertDialogTitle>
                                <AlertDialogDescription>
                                  "{conversation.title}" adlı sohbeti silmek istediğinizden emin misiniz? 
                                  Bu işlem geri alınamaz ve tüm mesajlar kalıcı olarak silinecektir.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>İptal</AlertDialogCancel>
                                <AlertDialogAction
                                  className="bg-red-600 hover:bg-red-700"
                                  onClick={() => onDeleteConversation(conversation.id)}
                                >
                                  Sil
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Empty State */}
            {conversations.length === 0 && (
              <div className="text-center py-12 px-4">
                <div className="bg-gray-100 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4">
                  <MessageSquare className="h-8 w-8 text-gray-400" />
                </div>
                <p className="text-sm font-medium text-gray-600">Henüz sohbet yok</p>
                <p className="text-xs text-gray-400 mt-2">
                  Sağlık sigortası hakkında soru sormak için
                  <br />
                  yukarıdaki butona tıklayın
                </p>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="mt-4"
                  onClick={onNewConversation}
                >
                  <MessageSquarePlus className="h-4 w-4 mr-2" />
                  İlk Sohbeti Başlat
                </Button>
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </TooltipProvider>
  );
}
