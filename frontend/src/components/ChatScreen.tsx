import { useState, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ScrollArea } from './ui/scroll-area';
import { Card } from './ui/card';
import { ChatMessage } from './ChatMessage';
import { ChatHistory } from './ChatHistory';
import { RenameDialog } from './RenameDialog';
import { Send, LogOut, HeartPulse, Menu, X } from 'lucide-react';
import { Separator } from './ui/separator';
import { chatRequest } from '../api/ChatApi';
import { Message, Conversation, ConversationData, createQueryRequest } from '../models';

interface ChatScreenProps {
  userEmail: string;
  userName: string;
  onLogout: () => void;
  onOpenProfile: () => void;
}

async function getResponseForQuery(query: string): Promise<string> {
  const request = createQueryRequest(query);

  try {
    const response = await chatRequest(request);
    return response.answer;
  } catch (error) {
    console.error('Chat request failed:', error);
    return "Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.";
  }
}

const createInitialMessage = (): Message => ({
  id: crypto.randomUUID(),
  content: "Merhaba! Ben sağlık sigortası asistanınızım. Size nasıl yardımcı olabilirim?",
  sender: 'agent',
  timestamp: new Date()
});

export function ChatScreen({ userEmail, userName, onLogout, onOpenProfile }: ChatScreenProps) {
  const [conversations, setConversations] = useState<ConversationData[]>([
    { id: crypto.randomUUID(), messages: [createInitialMessage()] }
  ]);
  const [currentConversationId, setCurrentConversationId] = useState<string>(conversations[0].id);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const currentConversation = conversations.find(c => c.id === currentConversationId);
  const messages = currentConversation?.messages || [];

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const addMessage = (message: Message) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === currentConversationId
          ? { ...conv, messages: [...conv.messages, message] }
          : conv
      )
    );
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      content: input.trim(),
      sender: 'user',
      timestamp: new Date()
    };

    addMessage(userMessage);
    const queryText = input.trim();
    setInput('');
    setIsTyping(true);

    try {
      const response = await getResponseForQuery(queryText);

      const agentMessage: Message = {
        id: crypto.randomUUID(),
        content: response,
        sender: 'agent',
        timestamp: new Date()
      };

      addMessage(agentMessage);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewConversation = () => {
    const newId = crypto.randomUUID();
    const newConversation: ConversationData = {
      id: newId,
      messages: [createInitialMessage()]
    };
    setConversations(prev => [newConversation, ...prev]);
    setCurrentConversationId(newId);
  };

  const handleSelectConversation = (id: string) => {
    setCurrentConversationId(id);
  };

  const handleDeleteConversation = (id: string) => {
    if (conversations.length === 1) {
      // Don't delete the last conversation, just reset it
      const newConversation: ConversationData = {
        id: crypto.randomUUID(),
        messages: [createInitialMessage()]
      };
      setConversations([newConversation]);
      setCurrentConversationId(newConversation.id);
      return;
    }

    const remainingConversations = conversations.filter(c => c.id !== id);
    setConversations(remainingConversations);
    
    if (currentConversationId === id) {
      setCurrentConversationId(remainingConversations[0].id);
    }
  };

  const handleRenameConversation = (id: string) => {
    setRenamingConversationId(id);
    setRenameDialogOpen(true);
  };

  const handleRenameSubmit = (newTitle: string) => {
    if (renamingConversationId && newTitle.trim()) {
      setConversations(prev =>
        prev.map(conv =>
          conv.id === renamingConversationId
            ? { ...conv, customTitle: newTitle.trim() }
            : conv
        )
      );
    }
    setRenamingConversationId(null);
  };

  const getConversationTitle = (conv: ConversationData): string => {
    if (conv.customTitle) return conv.customTitle;
    
    const firstUserMessage = conv.messages.find(m => m.sender === 'user');
    if (firstUserMessage) {
      const maxLength = 50;
      return firstUserMessage.content.length > maxLength
        ? `${firstUserMessage.content.slice(0, maxLength)}...`
        : firstUserMessage.content;
    }
    
    return 'Yeni Sohbet';
  };

  const getLastMessagePreview = (conv: ConversationData): string => {
    const userMessages = conv.messages.filter(m => m.sender === 'user');
    const lastUserMessage = userMessages[userMessages.length - 1];
    
    if (!lastUserMessage) return 'Henüz mesaj yok';
    
    const maxLength = 60;
    return lastUserMessage.content.length > maxLength
      ? `${lastUserMessage.content.slice(0, maxLength)}...`
      : lastUserMessage.content;
  };

  const conversationsList: Conversation[] = conversations.map(conv => ({
    id: conv.id,
    title: getConversationTitle(conv),
    lastMessage: getLastMessagePreview(conv),
    timestamp: conv.messages[conv.messages.length - 1]?.timestamp || new Date(),
    messageCount: conv.messages.length
  }));

  const renamingConversation = renamingConversationId
    ? conversationsList.find(c => c.id === renamingConversationId)
    : null;

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar - Toggleable */}
      {sidebarOpen && (
        <aside className="h-full flex-shrink-0 bg-white">
          <ChatHistory
            conversations={conversationsList}
            currentConversationId={currentConversationId}
            onSelectConversation={handleSelectConversation}
            onNewConversation={handleNewConversation}
            onDeleteConversation={handleDeleteConversation}
            onRenameConversation={handleRenameConversation}
          />
        </aside>
      )}

      {/* Rename Dialog */}
      <RenameDialog
        open={renameDialogOpen}
        currentTitle={renamingConversation?.title || ''}
        onOpenChange={setRenameDialogOpen}
        onRename={handleRenameSubmit}
      />

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label={sidebarOpen ? 'Menüyü kapat' : 'Menüyü aç'}
                className="mr-2"
              >
                {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </Button>
              <div className="h-10 w-10 bg-blue-600 rounded-full flex items-center justify-center">
                <HeartPulse className="h-6 w-6 text-white" />
              </div>
              <h1 className="text-lg font-semibold">
                Sağlık Sigortası Asistanı
              </h1>
            </div>

            <div className="flex items-center gap-2">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={onOpenProfile}
                aria-label="Profil ayarları"
              >
                <span className="text-sm text-gray-600">
                  {userName}
                </span>
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={onLogout}
                aria-label="Çıkış yap"
              >
                <LogOut className="h-4 w-4 mr-2" />
                Çıkış Yap
              </Button>
            </div>
          </div>
        </header>

        {/* Chat Area */}
        <div className="flex-1 overflow-hidden p-6">
          <Card className="h-full flex flex-col max-w-5xl mx-auto">
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {messages.map(message => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                
                {isTyping && (
                  <ChatMessage 
                    message={{
                      id: 'typing',
                      content: '',
                      sender: 'agent',
                      timestamp: new Date(),
                      isLoading: true
                    }} 
                  />
                )}
                
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            <Separator />

            {/* Input Area */}
            <div className="p-4 flex-shrink-0">
              <div className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Sağlık sigortanızla ilgili sorunuzu yazın..."
                  disabled={isTyping}
                  aria-label="Mesaj yazın"
                  className="flex-1"
                />
                <Button 
                  onClick={handleSend} 
                  disabled={!input.trim() || isTyping}
                  aria-label="Mesaj gönder"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-gray-500 mt-2 text-center">
                Sağlık asistanınızla güvenli ve gizli bir şekilde iletişim kurabilirsiniz.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}