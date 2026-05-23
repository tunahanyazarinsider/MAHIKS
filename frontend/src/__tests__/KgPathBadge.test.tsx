import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KgPathBadge } from '../components/KgPathBadge';
import type { GraphFact } from '../models';

describe('KgPathBadge', () => {
  it('renders a triplet as two pills and one relation label', () => {
    const fact: GraphFact = {
      type: 'triplet',
      source: 'Astım',
      rel: 'TREATED_BY',
      target: 'Beklometazon',
    };
    const { container } = render(<KgPathBadge fact={fact} />);

    expect(screen.getByText('Astım')).toBeInTheDocument();
    expect(screen.getByText('Beklometazon')).toBeInTheDocument();
    expect(screen.getByText('TREATED_BY')).toBeInTheDocument();

    // 2 pills (source, target) + 1 rel label rendered between them
    const pills = container.querySelectorAll('.rounded-full');
    expect(pills).toHaveLength(2);
  });

  it('renders a multi-hop path as N pills interleaved with N-1 rel labels', () => {
    const fact: GraphFact = {
      type: 'path',
      nodes: ['Diabet', 'Metformin', 'Plan A'],
      rels: ['TREATED_BY', 'COVERS'],
    };
    const { container } = render(<KgPathBadge fact={fact} />);

    expect(screen.getByText('Diabet')).toBeInTheDocument();
    expect(screen.getByText('Metformin')).toBeInTheDocument();
    expect(screen.getByText('Plan A')).toBeInTheDocument();
    expect(screen.getByText('TREATED_BY')).toBeInTheDocument();
    expect(screen.getByText('COVERS')).toBeInTheDocument();

    const pills = container.querySelectorAll('.rounded-full');
    expect(pills).toHaveLength(3);
  });

  it('handles a triplet with missing fields by substituting question marks', () => {
    const fact = { type: 'triplet', source: 'X', rel: '', target: '' } as GraphFact;
    render(<KgPathBadge fact={fact} />);
    expect(screen.getByText('X')).toBeInTheDocument();
  });

  it('renders nothing when path has no nodes', () => {
    const fact: GraphFact = { type: 'path', nodes: [], rels: [] };
    const { container } = render(<KgPathBadge fact={fact} />);
    expect(container).toBeEmptyDOMElement();
  });
});
