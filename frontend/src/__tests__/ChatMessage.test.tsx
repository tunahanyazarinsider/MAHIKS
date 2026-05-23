import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatMessage } from '../components/ChatMessage';
import type { Message } from '../models';

function makeAgentMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: 'msg-1',
    sender: 'agent',
    content: 'Astım tedavisinde kombinasyon ilaçları kullanılır [1]. Reçete… [2].',
    timestamp: new Date('2026-05-22T10:00:00Z'),
    citations: [
      { index: 1, source: 'SUT', section_number: '1.5.1', content: 'Astım reçeteleri…' },
      { index: 2, source: 'SUT', section_number: '2.3', content: 'Kombinasyon kuralları…' },
    ],
    backendId: 42,
    ...overrides,
  };
}

describe('ChatMessage', () => {
  it('renders [N] markers as clickable citation badges', () => {
    const message = makeAgentMessage();
    render(<ChatMessage message={message} />);

    const badge1 = screen.getByRole('button', { name: 'Kaynak 1' });
    const badge2 = screen.getByRole('button', { name: 'Kaynak 2' });
    expect(badge1).toBeInTheDocument();
    expect(badge2).toBeInTheDocument();
    expect(badge1).toHaveTextContent('1');
    expect(badge2).toHaveTextContent('2');
  });

  it('clicking a citation badge keeps the citations panel open', async () => {
    const user = userEvent.setup();
    const message = makeAgentMessage();
    render(<ChatMessage message={message} />);

    // Panel auto-opens because content has [N] — verify a citation row is visible.
    expect(screen.getByText(/Astım reçeteleri/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Kaynak 2' }));
    // After click, panel still shows the second citation content.
    expect(screen.getByText(/Kombinasyon kuralları/)).toBeInTheDocument();
  });

  it('shows the low-confidence amber banner when confidence.level === "low"', () => {
    const message = makeAgentMessage({
      content: 'Bu konuda elimdeki bilgiler kısıtlı.',
      citations: [],
      confidence: {
        level: 'low',
        max_ce: -5.1,
        mean_ce: -7.0,
        passed_chunks: 1,
        ce_floor: 0,
        min_chunks: 2,
      },
    });
    render(<ChatMessage message={message} />);

    expect(screen.getByText(/Düşük kaynak güveni/)).toBeInTheDocument();
    expect(screen.getByText(/SGK ALO 170/)).toBeInTheDocument();
  });

  it('does not show low-confidence banner for normal confidence', () => {
    const message = makeAgentMessage({
      confidence: {
        level: 'normal',
        max_ce: 0.8,
        mean_ce: 0.5,
        passed_chunks: 5,
        ce_floor: 0,
        min_chunks: 2,
      },
    });
    render(<ChatMessage message={message} />);
    expect(screen.queryByText(/Düşük kaynak güveni/)).not.toBeInTheDocument();
  });

  it('renders thumbs but disables them when backendId is missing', () => {
    const message = makeAgentMessage({ backendId: undefined });
    const onFeedback = vi.fn();
    render(<ChatMessage message={message} onFeedback={onFeedback} />);

    const thumbUp = screen.getByRole('button', { name: 'Bu yanıtı beğen' });
    const thumbDown = screen.getByRole('button', { name: 'Bu yanıtı beğenme' });
    expect(thumbUp).toBeDisabled();
    expect(thumbDown).toBeDisabled();
  });

  it('thumbs-down click reveals the reason form and Gönder submits with the text', async () => {
    const user = userEvent.setup();
    const message = makeAgentMessage();
    const onFeedback = vi.fn().mockResolvedValue(undefined);
    render(<ChatMessage message={message} onFeedback={onFeedback} />);

    const thumbDown = screen.getByRole('button', { name: 'Bu yanıtı beğenme' });
    await user.click(thumbDown);

    const textarea = screen.getByPlaceholderText(/kaynak eksik/i);
    expect(textarea).toBeInTheDocument();
    await user.type(textarea, 'yanıt eksik');

    await user.click(screen.getByRole('button', { name: 'Gönder' }));

    expect(onFeedback).toHaveBeenCalledWith('down', 'yanıt eksik');
  });

  it('thumbs-up click submits "up" feedback immediately without reason', async () => {
    const user = userEvent.setup();
    const message = makeAgentMessage();
    const onFeedback = vi.fn().mockResolvedValue(undefined);
    render(<ChatMessage message={message} onFeedback={onFeedback} />);

    await user.click(screen.getByRole('button', { name: 'Bu yanıtı beğen' }));
    expect(onFeedback).toHaveBeenCalledWith('up');
  });

  it('shows existing feedback state via aria-pressed', () => {
    const message = makeAgentMessage({ feedback: 'down' });
    const onFeedback = vi.fn();
    render(<ChatMessage message={message} onFeedback={onFeedback} />);

    const thumbDown = screen.getByRole('button', { name: 'Bu yanıtı beğenme' });
    expect(thumbDown).toHaveAttribute('aria-pressed', 'true');

    const thumbUp = screen.getByRole('button', { name: 'Bu yanıtı beğen' });
    expect(thumbUp).toHaveAttribute('aria-pressed', 'false');
  });

  it('renders user messages plain — no markdown, no thumbs, no citation panel', () => {
    const message: Message = {
      id: 'u1',
      sender: 'user',
      content: 'SGK katkı payı oranı nedir? [1]',
      timestamp: new Date(),
    };
    const onFeedback = vi.fn();
    render(<ChatMessage message={message} onFeedback={onFeedback} />);

    // For user messages, [1] is rendered literally (no citation badge).
    expect(screen.getByText(/SGK katkı payı oranı nedir\? \[1\]/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Kaynak/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Bu yanıtı beğen' })).not.toBeInTheDocument();
  });
});
