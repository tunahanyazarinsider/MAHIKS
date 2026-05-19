import { useState, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ChatMessage } from './ChatMessage';
import { ChatHistory } from './ChatHistory';
import { RagInfoScreen } from './RagInfoScreen';
import { EvalDashboard } from './EvalDashboard';
import { RenameDialog } from './RenameDialog';
import { DeleteDialog } from './DeleteDialog';
import { Send, LogOut, HeartPulse, Loader2, ArrowUp } from 'lucide-react';
import { chatRequestStream } from '../api/ChatApi';
import {
  createConversation,
  getConversations,
  getConversation,
  updateConversationTitle,
  deleteConversation as deleteConversationApi,
  addMessage,
  submitFeedback,
  ConversationResponse,
  MessageResponse
} from '../api/ConversationApi';
import { Message, Conversation, ConfidenceInfo, RagMetadata, createQueryRequest } from '../models';

interface ChatScreenProps {
  userEmail: string;
  userName: string;
  onLogout: () => void;
  onOpenProfile: () => void;
}

const SUGGESTION_CHIPS = [
  "Sağlık sigortası kapsamında neler var?",
  "Ameliyat masrafları nasıl karşılanır?",
  "Reçete ilaçları için ne kadar ödenir?",
  "Özel hastane farkı nedir?",
];

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
  const [showRagInfo, setShowRagInfo] = useState(false);
  const [showEvalDashboard, setShowEvalDashboard] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const streamingStartedRef = useRef(false);

  useEffect(() => {
    loadConversations();
  }, []);

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
      if (convs.length > 0) {
        await loadConversation(convs[0].id);
      } else {
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
      setIsTyping(false);
      streamingStartedRef.current = false;
      const formattedMessages: Message[] = conv.messages.map((msg: MessageResponse) => ({
        id: msg.id.toString(),
        backendId: msg.id,
        content: msg.content,
        sender: msg.sender,
        timestamp: new Date(msg.created_at),
        feedback: msg.feedback ?? null,
        citations: msg.citations
          ? msg.citations.map((c, i) => ({
              index: c.index ?? i + 1,
              source: c.source,
              section_number: c.section_number,
              section_title: c.section_title,
              content: c.content ?? '',
              relevance_score: c.relevance_score,
              document_type: c.document_type as ('pdf' | 'html' | 'txt' | undefined),
            }))
          : undefined,
      }));
      setMessages(formattedMessages);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleSend = async (overrideInput?: string) => {
    const messageContent = (overrideInput || input).trim();
    if (!messageContent || isTyping || !currentConversationId) return;

    setInput('');

    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      content: messageContent,
      sender: 'user',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, tempUserMessage]);
    setIsTyping(true);

    const agentMsgId = `agent-${Date.now()}`;
    streamingStartedRef.current = false;
    // SSE events (metadata, confidence, citations) can arrive before the
    // first chunk creates the agent message. We capture them in closure
    // variables and attach them when the message is actually inserted.
    let streamedCitations: Message['citations'] | undefined;
    let streamedMetadata: RagMetadata | undefined;
    let streamedConfidence: ConfidenceInfo | undefined;

    try {
      await addMessage(currentConversationId, messageContent, 'user');

      const request = createQueryRequest(messageContent, {
        conversation_id: currentConversationId?.toString(),
      });

      await chatRequestStream(
        request,
        (chunk) => {
          if (!streamingStartedRef.current) {
            streamingStartedRef.current = true;
            setMessages(prev => [...prev, {
              id: agentMsgId,
              content: chunk,
              sender: 'agent',
              timestamp: new Date(),
              ragMetadata: streamedMetadata,
              confidence: streamedConfidence,
            }]);
          } else {
            setMessages(prev => prev.map(m =>
              m.id === agentMsgId ? { ...m, content: m.content + chunk } : m
            ));
          }
        },
        // onMetadata — capture and (if the message already exists) attach.
        (metadata) => {
          streamedMetadata = metadata as RagMetadata;
          setMessages(prev => prev.map(m =>
            m.id === agentMsgId
              ? { ...m, ragMetadata: streamedMetadata }
              : m
          ));
        },
        (citations) => {
          streamedCitations = citations.map((c: any, i: number) => ({
            index: c.index ?? i + 1,
            source: c.source,
            section_number: c.section_number,
            section_title: c.section_title,
            content: c.content ?? '',
            relevance_score: c.relevance_score ?? c.similarity,
            document_type: c.document_type,
          }));
          setMessages(prev => prev.map(m =>
            m.id === agentMsgId
              ? { ...m, citations: streamedCitations }
              : m
          ));
        },
        async (data) => {
          // Attach graph facts (sent on the `done` event by the orchestrator)
          // so the RAG-details panel can render the KG pill chains.
          const graphFacts = data.graph_facts as Message['graphFacts'];
          if (graphFacts && graphFacts.length) {
            setMessages(prev => prev.map(m =>
              m.id === agentMsgId ? { ...m, graphFacts } : m,
            ));
          }
          if (data.answer) {
            const savedId = await addMessage(
              currentConversationId,
              data.answer,
              'agent',
              streamedCitations,
            );
            // Attach the backend id so feedback submission can target the row.
            setMessages(prev => prev.map(m =>
              m.id === agentMsgId ? { ...m, backendId: savedId } : m
            ));
          }
          const currentConv = conversations.find(c => c.id === currentConversationId);
          if (currentConv && currentConv.title === 'Yeni Sohbet') {
            const newTitle = messageContent.slice(0, 30) + (messageContent.length > 30 ? '...' : '');
            await updateConversationTitle(currentConversationId, newTitle);
            setConversations(prev =>
              prev.map(c => c.id === currentConversationId ? { ...c, title: newTitle } : c)
            );
          }
          const updatedConvs = await getConversations();
          setConversations(updatedConvs);
        },
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
        },
        // onConfidence — show the amber "low confidence" banner before tokens arrive.
        (data) => {
          streamedConfidence = data;
          setMessages(prev => prev.map(m =>
            m.id === agentMsgId ? { ...m, confidence: data } : m
          ));
        },
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

  const handleFeedback = async (
    message: Message,
    rating: 'up' | 'down',
    reason?: string,
  ) => {
    if (!currentConversationId || !message.backendId) return;
    const previous = message.feedback ?? null;
    // Optimistic update so the UI feels instant.
    setMessages(prev => prev.map(m =>
      m.id === message.id ? { ...m, feedback: rating } : m,
    ));
    try {
      await submitFeedback(currentConversationId, message.backendId, rating, reason);
    } catch (err) {
      console.error('Failed to submit feedback:', err);
      // Revert on failure.
      setMessages(prev => prev.map(m =>
        m.id === message.id ? { ...m, feedback: previous } : m,
      ));
    }
  };

  const handleNewConversation = async () => {
    try {
      setShowRagInfo(false);
      setShowEvalDashboard(false);
      const newConvId = await createConversation();
      const updatedConvs = await getConversations();
      setConversations(updatedConvs);
      await loadConversation(newConvId);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = async (id: string) => {
    setShowRagInfo(false);
    setShowEvalDashboard(false);
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
          conv.id === renamingConversationId ? { ...conv, title: newTitle.trim() } : conv
        )
      );
    } catch (error) {
      console.error('Failed to rename conversation:', error);
    } finally {
      setRenamingConversationId(null);
    }
  };

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
      <div className="flex h-screen w-screen items-center justify-center bg-[#f8faf9]">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="h-12 w-12 rounded-full bg-gradient-to-br from-[#047857] to-[#065f46] flex items-center justify-center">
              <HeartPulse className="h-6 w-6 text-white" />
            </div>
            <Loader2 className="h-14 w-14 animate-spin text-[#047857]/30 absolute -top-1 -left-1" />
          </div>
          <p className="text-[#5f7068] text-sm">Yükleniyor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#f8faf9]">
      {/* Sidebar */}
      <div className="w-[280px] shrink-0 border-r border-[#e2e8e5] bg-[#fafcfb] hidden md:block">
        <ChatHistory
          conversations={conversationsList}
          currentConversationId={currentConversationId?.toString() || null}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          onShowRagInfo={() => { setShowRagInfo(true); setShowEvalDashboard(false); }}
          onShowEvalDashboard={() => { setShowEvalDashboard(true); setShowRagInfo(false); }}
        />
      </div>

      <RenameDialog
        open={renameDialogOpen}
        currentTitle={renamingConversation?.title || ''}
        onOpenChange={setRenameDialogOpen}
        onRename={handleRenameSubmit}
      />
      <DeleteDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
      />

      {/* Main Content Area */}
      {showEvalDashboard ? (
        <EvalDashboard onBack={() => setShowEvalDashboard(false)} />
      ) : showRagInfo ? (
        <RagInfoScreen onBack={() => setShowRagInfo(false)} />
      ) : (
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white/80 backdrop-blur-sm border-b border-[#e2e8e5] px-6 py-3 shrink-0">
          <div className="flex items-center justify-between max-w-[900px] mx-auto w-full">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 bg-gradient-to-br from-[#047857] to-[#065f46] rounded-xl flex items-center justify-center shadow-sm">
                <HeartPulse className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-[15px] font-semibold text-[#1a2e28] leading-tight" style={{ fontFamily: 'var(--font-serif)' }}>
                  Sağlık Sigortası Asistanı
                </h1>
                <p className="text-[11px] text-[#9aada2]">Yapay zeka destekli</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={onOpenProfile}
                className="text-[13px] text-[#5f7068] hover:text-[#1a2e28] transition-colors px-2 py-1 rounded-lg hover:bg-[#f1f5f3]"
              >
                {userName}
              </button>
              <button
                onClick={onLogout}
                className="flex items-center gap-1.5 text-[13px] text-[#5f7068] hover:text-[#1a2e28] transition-colors px-2.5 py-1.5 rounded-lg hover:bg-[#f1f5f3] border border-[#e2e8e5]"
              >
                <LogOut className="h-3.5 w-3.5" />
                Çıkış
              </button>
            </div>
          </div>
        </header>

        {/* Messages Area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-[800px] mx-auto px-6 py-6">
            {messages.length === 0 && !isTyping ? (
              /* Welcome State */
              <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
                <div className="w-20 h-20 bg-gradient-to-br from-[#ecfdf5] to-[#d1fae5] rounded-2xl flex items-center justify-center mb-6 shadow-sm">
                  <HeartPulse className="h-10 w-10 text-[#047857]" />
                </div>
                <h2 className="text-2xl font-semibold text-[#1a2e28] mb-2" style={{ fontFamily: 'var(--font-serif)' }}>
                  Hoş Geldiniz
                </h2>
                <p className="text-[#5f7068] mb-8 max-w-md leading-relaxed">
                  Sağlık sigortanız hakkında sorularınızı sorabilirsiniz. Size en doğru bilgiyi kaynaklardan bularak yanıtlayacağım.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
                  {SUGGESTION_CHIPS.map((suggestion, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(suggestion)}
                      className="text-[13px] text-left p-4 rounded-xl bg-white border border-[#e2e8e5] hover:border-[#a7f3d0] hover:bg-[#f0fdf4] transition-all shadow-sm hover:shadow group"
                    >
                      <span className="text-[#1a2e28] group-hover:text-[#047857] transition-colors">{suggestion}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-5">
                {messages.map(message => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    onFeedback={
                      message.sender === 'agent' && !message.isLoading
                        ? (rating, reason) => handleFeedback(message, rating, reason)
                        : undefined
                    }
                  />
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
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="shrink-0 border-t border-[#e2e8e5] bg-white/80 backdrop-blur-sm">
          <div className="max-w-[800px] mx-auto px-6 py-4">
            <div className="flex gap-3 items-end">
              <div className="flex-1 relative">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Sağlık sigortanızla ilgili sorunuzu yazın..."
                  disabled={isTyping}
                  className="w-full px-4 py-3 rounded-xl bg-[#f1f5f3] border border-[#e2e8e5] focus:border-[#047857] focus:ring-2 focus:ring-[#047857]/10 outline-none transition-all text-[15px] text-[#1a2e28] placeholder:text-[#9aada2] disabled:opacity-50"
                />
              </div>
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || isTyping}
                className="h-[46px] w-[46px] rounded-xl bg-[#047857] hover:bg-[#065f46] disabled:bg-[#d4ddd8] disabled:cursor-not-allowed text-white flex items-center justify-center transition-all shadow-sm hover:shadow"
              >
                <ArrowUp className="h-5 w-5" />
              </button>
            </div>
            <p className="text-[11px] text-[#9aada2] mt-2 text-center">
              Yanıtlar kaynaklara dayanmaktadır. Kesin bilgi için sigortacınıza danışın.
            </p>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
