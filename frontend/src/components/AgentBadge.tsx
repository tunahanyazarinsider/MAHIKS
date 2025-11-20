import { Badge } from './ui/badge';
import { Bot, FileText, DollarSign, Heart, Users } from 'lucide-react';

export type AgentType = 'coordinator' | 'claims' | 'billing' | 'coverage' | 'support';

interface AgentBadgeProps {
  type: AgentType;
}

const agentConfig = {
  coordinator: {
    label: 'Coordinator',
    icon: Users,
    className: 'bg-purple-100 text-purple-800 border-purple-200'
  },
  claims: {
    label: 'Claims Specialist',
    icon: FileText,
    className: 'bg-blue-100 text-blue-800 border-blue-200'
  },
  billing: {
    label: 'Billing Agent',
    icon: DollarSign,
    className: 'bg-green-100 text-green-800 border-green-200'
  },
  coverage: {
    label: 'Coverage Expert',
    icon: Heart,
    className: 'bg-red-100 text-red-800 border-red-200'
  },
  support: {
    label: 'Support Agent',
    icon: Bot,
    className: 'bg-gray-100 text-gray-800 border-gray-200'
  }
};

export function AgentBadge({ type }: AgentBadgeProps) {
  const config = agentConfig[type];
  const Icon = config.icon;

  return (
    <Badge variant="outline" className={config.className}>
      <Icon className="h-3 w-3 mr-1" />
      {config.label}
    </Badge>
  );
}
