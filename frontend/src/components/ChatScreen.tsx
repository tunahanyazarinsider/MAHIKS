import { useState, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ScrollArea } from './ui/scroll-area';
import { Card } from './ui/card';
import { ChatMessage, Message } from './ChatMessage';
import { ChatHistory, Conversation } from './ChatHistory';
import { RenameDialog } from './RenameDialog';
import { Send, LogOut, HeartPulse, Menu, X } from 'lucide-react';
import { Separator } from './ui/separator';
import { chatRequest } from '../api/ChatApi';
import { QueryRequest } from '../models/QueryRequest';

interface ChatScreenProps {
  userEmail: string;
  userName: string;
  onLogout: () => void;
  onOpenProfile: () => void;
}

async function getResponseForQuery(query: string): Promise<string> {

  const request = new QueryRequest(query);

  try {
    const response = await chatRequest(request);
    return response.answer;
  } catch (error) {
    console.error(error);
    return "I'm sorry, I couldn't understand your question.";
  }
}

const initialMessage: Message = {
  id: '1',
  content: "Hello! I'm your healthcare insurance assistant. I can help you with claims, billing, coverage questions, and general support. How can I assist you today?",
  sender: 'agent',
  timestamp: new Date()
};

interface ConversationData {
  id: string;
  messages: Message[];
  customTitle?: string;
}

export function ChatScreen({ userEmail, userName, onLogout, onOpenProfile }: ChatScreenProps) {
  const [conversations, setConversations] = useState<ConversationData[]>([
    { id: '1', messages: [initialMessage] }
  ]);
  const [currentConversationId, setCurrentConversationId] = useState<string>('1');
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const currentConversation = conversations.find(c => c.id === currentConversationId);
  const messages = currentConversation?.messages || [];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

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
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input,
      sender: 'user',
      timestamp: new Date()
    };

    addMessage(userMessage);

    setInput('');
    setIsTyping(true);

    try {
      const response = await getResponseForQuery(input);

      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: response,
        sender: 'agent',
        timestamp: new Date()
      };

      addMessage(agentMessage);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewConversation = () => {
    const newId = Date.now().toString();
    const newConversation: ConversationData = {
      id: newId,
      messages: [{ ...initialMessage, id: `${newId}-1`, timestamp: new Date() }]
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
      setConversations([{ id: '1', messages: [initialMessage] }]);
      setCurrentConversationId('1');
      return;
    }

    setConversations(prev => prev.filter(c => c.id !== id));
    if (currentConversationId === id) {
      const remainingConversations = conversations.filter(c => c.id !== id);
      setCurrentConversationId(remainingConversations[0]?.id || '1');
    }
  };

  const handleRenameConversation = (id: string) => {
    setRenamingConversationId(id);
    setRenameDialogOpen(true);
  };

  const handleRenameSubmit = (newTitle: string) => {
    if (renamingConversationId) {
      setConversations(prev =>
        prev.map(conv =>
          conv.id === renamingConversationId
            ? { ...conv, customTitle: newTitle }
            : conv
        )
      );
    }
    setRenamingConversationId(null);
  };

  const conversationsList: Conversation[] = conversations.map(conv => {
    const userMessages = conv.messages.filter(m => m.sender === 'user');
    const lastUserMessage = userMessages[userMessages.length - 1];
    const firstUserMessage = userMessages[0];

    const defaultTitle = firstUserMessage?.content.slice(0, 50) + (firstUserMessage?.content.length > 50 ? '...' : '') || 'New Conversation';

    return {
      id: conv.id,
      title: conv.customTitle || defaultTitle,
      lastMessage: lastUserMessage?.content.slice(0, 60) + (lastUserMessage?.content.length > 60 ? '...' : '') || 'No messages yet',
      timestamp: conv.messages[conv.messages.length - 1]?.timestamp || new Date(),
      messageCount: conv.messages.length
    };
  });

  const renamingConversation = renamingConversationId
    ? conversationsList.find(c => c.id === renamingConversationId)
    : null;

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      {sidebarOpen && (
        <ChatHistory
          conversations={conversationsList}
          currentConversationId={currentConversationId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
        />
      )}

      {/* Rename Dialog */}
      <RenameDialog
        open={renameDialogOpen}
        currentTitle={renamingConversation?.title || ''}
        onOpenChange={setRenameDialogOpen}
        onRename={handleRenameSubmit}
      />

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1">
        {/* Header */}
        <div className="bg-white border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="mr-2"
              >
                {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </Button>
              <div className="h-10 w-10 bg-blue-600 rounded-full flex items-center justify-center">
                <HeartPulse className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1>Healthcare Insurance Support</h1>
                <p className="text-sm text-gray-500">Multi-Agent Assistance</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <Button variant="ghost" size="sm" onClick={onOpenProfile}>
                <span className="text-sm text-gray-600">{userName}</span>
              </Button>
              <Button variant="outline" size="sm" onClick={onLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-hidden p-6">
          <Card className="h-full flex flex-col max-w-5xl mx-auto">
            <ScrollArea className="flex-1 p-4" ref={scrollRef}>
              <div className="space-y-4">
                {messages.map(message => (
                  <ChatMessage key={message.id} message={message} />
                ))}

                {isTyping && (
                  <div className="flex gap-3">
                    <div className="h-8 w-8 rounded-full bg-gray-200 flex items-center justify-center">
                      <div className="flex gap-1">
                        <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>

            <Separator />

            {/* Input Area */}
            <div className="p-4">
              <div className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask about claims, billing, coverage, or general support..."
                  className="flex-1"
                />
                <Button onClick={handleSend} disabled={!input.trim()}>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Ask me anything about your healthcare insurance
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
