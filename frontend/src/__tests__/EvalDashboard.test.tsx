import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the EvalApi module — we don't want real HTTP in unit tests.
vi.mock('../api/EvalApi', () => ({
  listReports: vi.fn(),
  getReport: vi.fn(),
}));

import { EvalDashboard, looksLikeEvalReport } from '../components/EvalDashboard';
import * as EvalApi from '../api/EvalApi';

describe('looksLikeEvalReport (shape validator)', () => {
  it('accepts a fully-shaped report', () => {
    const report = {
      summary: { retrieval: {}, generation: {} },
      results: [{ id: 'q1' }],
    };
    expect(looksLikeEvalReport(report)).toBe(true);
  });

  it('rejects null and primitives', () => {
    expect(looksLikeEvalReport(null)).toBe(false);
    expect(looksLikeEvalReport(undefined)).toBe(false);
    expect(looksLikeEvalReport('a string')).toBe(false);
    expect(looksLikeEvalReport(42)).toBe(false);
  });

  it('rejects objects missing summary.generation', () => {
    const report = {
      summary: { retrieval: {} },
      results: [],
    };
    expect(looksLikeEvalReport(report)).toBe(false);
  });

  it('rejects objects where results is not an array', () => {
    const report = {
      summary: { retrieval: {}, generation: {} },
      results: { not: 'an array' },
    };
    expect(looksLikeEvalReport(report)).toBe(false);
  });

  it('rejects empty objects', () => {
    expect(looksLikeEvalReport({})).toBe(false);
  });
});

describe('EvalDashboard — server-side report list', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the empty state when listReports returns []', async () => {
    vi.mocked(EvalApi.listReports).mockResolvedValueOnce([]);
    render(<EvalDashboard onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Henüz değerlendirme raporu yok/)).toBeInTheDocument();
    });
  });

  it('renders the run history table when listReports returns data', async () => {
    vi.mocked(EvalApi.listReports).mockResolvedValueOnce([
      {
        filename: 'eval_api_report_20260510_171446.json',
        timestamp: '2026-05-10T17:14:46Z',
        summary: {
          retrieval: {
            stage2_full_pipeline: { 'hit@1': 0.92, mrr: 0.9, 'ndcg@10': 0.95 },
            latency: { p95_ms: 8200 },
          },
          generation: {
            avg_faithfulness: 4.6,
            avg_context_precision: 4.2,
          },
        },
      } as any,
    ]);
    render(<EvalDashboard onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Koşum geçmişi/)).toBeInTheDocument();
    });
    // Stage2 Hit@1 = 0.92 formats to "0.920"
    expect(screen.getByText('0.920')).toBeInTheDocument();
    // Faithfulness 4.6 formats to "4.60"
    expect(screen.getByText('4.60')).toBeInTheDocument();
  });

  it('shows an error banner when listReports fails', async () => {
    vi.mocked(EvalApi.listReports).mockRejectedValueOnce(new Error('500 Internal'));
    render(<EvalDashboard onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/500 Internal/)).toBeInTheDocument();
    });
  });

  it('calls onBack when the back button is clicked', async () => {
    vi.mocked(EvalApi.listReports).mockResolvedValueOnce([]);
    const onBack = vi.fn();
    const user = userEvent.setup();
    render(<EvalDashboard onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByText(/Henüz değerlendirme raporu yok/)).toBeInTheDocument();
    });

    // Back button is the first button in the header (no accessible name).
    const buttons = screen.getAllByRole('button');
    await user.click(buttons[0]);
    expect(onBack).toHaveBeenCalled();
  });
});
