import { useState, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card } from './ui/card';
import { ChatMessage } from './ChatMessage';
import { ChatHistory } from './ChatHistory';
import { RenameDialog } from './RenameDialog';
import { DeleteDialog } from './DeleteDialog';
import { Send, LogOut, HeartPulse, Loader2 } from 'lucide-react';
import { Separator } from './ui/separator';
import { chatRequestStream } from '../api/ChatApi';
import { 
  createConversation, 
  getConversations, 
  getConversation,
  updateConversationTitle,
  deleteConversation as deleteConversationApi,
  addMessage,
  ConversationResponse,
  MessageResponse
} from '../api/ConversationApi';
import { Message, Conversation, createQueryRequest } from '../models';

interface ChatScreenProps {
  userEmail: string;
  userName: string;
  onLogout: () => void;
  onOpenProfile: () => void;
}

export function ChatScreen({ userEmail, userName, onLogout, onOpenProfile }: ChatScreenProps) {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [renamingConversationId, setRenamingConversationId] = useState<number | null>(null);
  const [deletingConversationId, setDeletingConversationId] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const streamingStartedRef = useRef(false);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const loadConversations = async () => {
    try {
      setIsLoading(true);
      const convs = await getConversations();
      setConversations(convs);
      
      // If there are conversations, load the first one
      if (convs.length > 0) {
        await loadConversation(convs[0].id);
      } else {
        // Create a new conversation if none exist
        await handleNewConversation();
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadConversation = async (conversationId: number) => {
    try {
      const conv = await getConversation(conversationId);
      setCurrentConversationId(conversationId);
      
      // Convert backend messages to frontend format
      const formattedMessages: Message[] = conv.messages.map((msg: MessageResponse) => ({
        id: msg.id.toString(),
        content: msg.content,
        sender: msg.sender,
        timestamp: new Date(msg.created_at)
      }));
      
      setMessages(formattedMessages);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping || !currentConversationId) return;

    const userMessageContent = input.trim();
    setInput('');

    // Add user message to UI immediately
    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      content: userMessageContent,
      sender: 'user',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, tempUserMessage]);
    setIsTyping(true);

    const agentMsgId = `agent-${Date.now()}`;
    streamingStartedRef.current = false;

    try {
      // Save user message to backend
      await addMessage(currentConversationId, userMessageContent, 'user');

      // Stream AI response
      const request = createQueryRequest(userMessageContent, {
        conversation_id: currentConversationId?.toString(),
      });

      await chatRequestStream(
        request,
        // onChunk: create agent message on first chunk, then append
        (chunk) => {
          if (!streamingStartedRef.current) {
            streamingStartedRef.current = true;
            setMessages(prev => [...prev, {
              id: agentMsgId,
              content: chunk,
              sender: 'agent',
              timestamp: new Date()
            }]);
          } else {
            setMessages(prev => prev.map(m =>
              m.id === agentMsgId
                ? { ...m, content: m.content + chunk }
                : m
            ));
          }
        },
        // onMetadata
        undefined,
        // onCitations
        undefined,
        // onDone: save the final answer to backend
        async (data) => {
          if (data.answer) {
            await addMessage(currentConversationId, data.answer, 'agent');
          }

          // Update conversation title if first message
          const currentConv = conversations.find(c => c.id === currentConversationId);
          if (currentConv && currentConv.title === 'Yeni Sohbet') {
            const newTitle = userMessageContent.slice(0, 30) + (userMessageContent.length > 30 ? '...' : '');
            await updateConversationTitle(currentConversationId, newTitle);
            setConversations(prev =>
              prev.map(c => c.id === currentConversationId ? { ...c, title: newTitle } : c)
            );
          }

          // Refresh conversations list
          const updatedConvs = await getConversations();
          setConversations(updatedConvs);
        },
        // onError
        (errorMsg) => {
          const errorContent = errorMsg || 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.';
          if (!streamingStartedRef.current) {
            streamingStartedRef.current = true;
            setMessages(prev => [...prev, {
              id: agentMsgId,
              content: errorContent,
              sender: 'agent',
              timestamp: new Date()
            }]);
          } else {
            setMessages(prev => prev.map(m =>
              m.id === agentMsgId ? { ...m, content: errorContent } : m
            ));
          }
        }
      );

    } catch (error) {
      console.error('Failed to send message:', error);
      const errorContent = 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.';
      if (!streamingStartedRef.current) {
        setMessages(prev => [...prev, {
          id: agentMsgId,
          content: errorContent,
          sender: 'agent',
          timestamp: new Date()
        }]);
      } else {
        setMessages(prev => prev.map(m =>
          m.id === agentMsgId ? { ...m, content: errorContent } : m
        ));
      }
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

  const handleNewConversation = async () => {
    try {
      const newConvId = await createConversation();
      const updatedConvs = await getConversations();
      setConversations(updatedConvs);
      await loadConversation(newConvId);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = async (id: string) => {
    await loadConversation(parseInt(id));
  };

  const handleDeleteConversation = (id: string) => {
    setDeletingConversationId(parseInt(id));
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingConversationId) return;

    try {
      await deleteConversationApi(deletingConversationId);
      
      const updatedConvs = await getConversations();
      setConversations(updatedConvs);
      
      // If we deleted the current conversation, load another one
      if (currentConversationId === deletingConversationId) {
        if (updatedConvs.length > 0) {
          await loadConversation(updatedConvs[0].id);
        } else {
          await handleNewConversation();
        }
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    } finally {
      setDeletingConversationId(null);
      setDeleteDialogOpen(false);
    }
  };

  const handleRenameConversation = (id: string) => {
    setRenamingConversationId(parseInt(id));
    setRenameDialogOpen(true);
  };

  const handleRenameSubmit = async (newTitle: string) => {
    if (!renamingConversationId || !newTitle.trim()) return;

    try {
      await updateConversationTitle(renamingConversationId, newTitle.trim());
      setConversations(prev =>
        prev.map(conv =>
          conv.id === renamingConversationId
            ? { ...conv, title: newTitle.trim() }
            : conv
        )
      );
    } catch (error) {
      console.error('Failed to rename conversation:', error);
    } finally {
      setRenamingConversationId(null);
    }
  };

  // Convert backend conversations to frontend format
  const conversationsList: Conversation[] = conversations.map(conv => ({
    id: conv.id.toString(),
    title: conv.title,
    lastMessage: conv.last_message || 'Henüz mesaj yok',
    timestamp: new Date(conv.updated_at),
    messageCount: conv.message_count
  }));

  const renamingConversation = renamingConversationId
    ? conversationsList.find(c => c.id === renamingConversationId.toString())
    : null;

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <p className="text-gray-600">Yükleniyor...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {/* Fixed Sidebar */}
      <div style={{ width: '280px', flexShrink: 0, borderRight: '1px solid #e5e7eb', backgroundColor: 'white' }}>
        <ChatHistory
          conversations={conversationsList}
          currentConversationId={currentConversationId?.toString() || null}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
        />
      </div>

      {/* Rename Dialog */}
      <RenameDialog
        open={renameDialogOpen}
        currentTitle={renamingConversation?.title || ''}
        onOpenChange={setRenameDialogOpen}
        onRename={handleRenameSubmit}
      />

      {/* Delete Dialog */}
      <DeleteDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
      />

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', backgroundColor: '#f9fafb' }}>
        {/* Header */}
        <header style={{ backgroundColor: 'white', borderBottom: '1px solid #e5e7eb', padding: '16px 24px', flexShrink: 0 }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-blue-600 rounded-full flex items-center justify-center">
                <HeartPulse className="h-6 w-6 text-white" />
              </div>
              <h1 className="text-lg font-semibold">Sağlık Sigortası Asistanı</h1>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={onOpenProfile}>
                <span className="text-sm text-gray-600">{userName}</span>
              </Button>
              <Button variant="outline" size="sm" onClick={onLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Çıkış Yap
              </Button>
            </div>
          </div>
        </header>

        {/* Chat Area */}
        <div style={{ flex: 1, overflow: 'hidden', padding: '24px' }}>
          <Card className="h-full flex flex-col" style={{ maxWidth: '900px', margin: '0 auto' }}>
            {/* Messages */}
            <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
              <div className="space-y-4">
                {messages.map(message => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                
                {isTyping && !streamingStartedRef.current && (
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
              </div>
            </div>

            <Separator />

            {/* Input */}
            <div style={{ padding: '16px', flexShrink: 0 }}>
              <div className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Sağlık sigortanızla ilgili sorunuzu yazın..."
                  disabled={isTyping}
                  className="flex-1"
                />
                <Button onClick={handleSend} disabled={!input.trim() || isTyping}>
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