import { ArrowRight } from 'lucide-react';
import type { GraphFact } from '../models';

interface KgPathBadgeProps {
  fact: GraphFact;
}

function Pill({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-[#ecfdf5] text-[#047857] border border-[#a7f3d0] text-[11px] font-medium max-w-[180px] truncate">
      {label}
    </span>
  );
}

function RelLabel({ label }: { label: string }) {
  return (
    <span className="text-[10px] font-mono text-[#5f7068] uppercase tracking-wide">
      {label}
    </span>
  );
}

/**
 * Render a knowledge-graph fact (triplet or path) as a horizontal pill chain.
 *
 *   Triplet: [source] → REL → [target]
 *   Path:    [n0] → REL0 → [n1] → REL1 → [n2] ...
 */
export function KgPathBadge({ fact }: KgPathBadgeProps) {
  // Normalize both fact shapes into one nodes + rels sequence.
  const nodes: string[] = [];
  const rels: string[] = [];

  if (fact.type === 'triplet') {
    nodes.push(fact.source ?? '?');
    rels.push(fact.rel ?? '');
    nodes.push(fact.target ?? '?');
  } else if (fact.type === 'path') {
    for (const n of fact.nodes ?? []) nodes.push(n);
    for (const r of fact.rels ?? []) rels.push(r);
  }

  if (nodes.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5 flex-wrap py-1">
      {nodes.map((node, i) => (
        <span key={i} className="inline-flex items-center gap-1.5">
          <Pill label={node} />
          {i < rels.length && (
            <>
              <ArrowRight className="h-3 w-3 text-[#9aada2]" />
              <RelLabel label={rels[i]} />
              <ArrowRight className="h-3 w-3 text-[#9aada2]" />
            </>
          )}
        </span>
      ))}
    </div>
  );
}
