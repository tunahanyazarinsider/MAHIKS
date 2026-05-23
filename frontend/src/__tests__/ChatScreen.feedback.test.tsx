import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock both API modules at the module level so ChatScreen never hits the
// real HTTP layer. Setting up here (before the component import) ensures
// vi.mock factories run first.
vi.mock('../api/ConversationApi', () => ({
  getConversations: vi.fn(),
  getConversation: vi.fn(),
  createConversation: vi.fn(),
  updateConversationTitle: vi.fn(),
  deleteConversation: vi.fn(),
  addMessage: vi.fn(),
  submitFeedback: vi.fn(),
}));

vi.mock('../api/ChatApi', () => ({
  chatRequestStream: vi.fn(),
}));

import { ChatScreen } from '../components/ChatScreen';
import * as ConversationApi from '../api/ConversationApi';

const SEEDED_CONVO = {
  id: 1,
  user_id: 1,
  title: 'Test sohbet',
  created_at: '2026-05-22T10:00:00Z',
  updated_at: '2026-05-22T10:00:00Z',
  messages: [
    {
      id: 100,
      conversation_id: 1,
      content: 'Sağlık sigortası nedir?',
      sender: 'user' as const,
      created_at: '2026-05-22T10:00:00Z',
    },
    {
      id: 101,
      conversation_id: 1,
      content: 'Sağlık sigortası, beklenmedik tıbbi giderleri karşılar.',
      sender: 'agent' as const,
      created_at: '2026-05-22T10:00:05Z',
      feedback: null,
      citations: [{ index: 1, source: 'SUT', content: 'Genel hükümler' }],
    },
  ],
};

describe('ChatScreen — feedback round-trip', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ConversationApi.getConversations).mockResolvedValue([
      { id: 1, user_id: 1, title: 'Test sohbet', message_count: 2, last_message: '…', created_at: '', updated_at: '' },
    ]);
    vi.mocked(ConversationApi.getConversation).mockResolvedValue(SEEDED_CONVO);
  });

  const renderAndWait = async () => {
    const utils = render(
      <ChatScreen
        userEmail="test@mahiks.local"
        userName="Test"
        onLogout={() => {}}
        onOpenProfile={() => {}}
      />,
    );
    // Wait for the seeded conversation to render (agent message visible).
    await waitFor(() => {
      expect(screen.getByText(/Sağlık sigortası, beklenmedik/)).toBeInTheDocument();
    });
    return utils;
  };

  it('clicking thumbs-up calls submitFeedback with the message backendId and "up"', async () => {
    vi.mocked(ConversationApi.submitFeedback).mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    await renderAndWait();

    const thumbUp = screen.getByRole('button', { name: 'Bu yanıtı beğen' });
    await user.click(thumbUp);

    await waitFor(() => {
      expect(ConversationApi.submitFeedback).toHaveBeenCalledWith(1, 101, 'up', undefined);
    });
  });

  it('optimistically updates aria-pressed on thumbs-up click, before the API resolves', async () => {
    // Hold the resolution so we can observe the optimistic state.
    let resolveFn: (v: undefined) => void = () => {};
    vi.mocked(ConversationApi.submitFeedback).mockImplementationOnce(
      () => new Promise<void>(res => { resolveFn = res; }),
    );
    const user = userEvent.setup();
    await renderAndWait();

    const thumbUp = screen.getByRole('button', { name: 'Bu yanıtı beğen' });
    await user.click(thumbUp);

    // While the promise is still pending, the optimistic update should already
    // have set aria-pressed=true on the thumb-up button.
    await waitFor(() => {
      expect(thumbUp).toHaveAttribute('aria-pressed', 'true');
    });

    resolveFn(undefined);
  });

  it('rolls back the optimistic state when submitFeedback rejects', async () => {
    vi.mocked(ConversationApi.submitFeedback).mockRejectedValueOnce(new Error('500 Internal'));
    // Silence the console.error from the rollback path.
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const user = userEvent.setup();
    await renderAndWait();

    const thumbUp = screen.getByRole('button', { name: 'Bu yanıtı beğen' });
    await user.click(thumbUp);

    // After the rejection settles, aria-pressed should be back to "false"
    // (the original message had feedback: null).
    await waitFor(() => {
      expect(thumbUp).toHaveAttribute('aria-pressed', 'false');
    });

    errSpy.mockRestore();
  });
});
