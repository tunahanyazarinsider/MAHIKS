// Re-export for backward compatibility
export { 
  type QueryRequest, 
  createQueryRequest 
} from './index';

// Legacy class support (deprecated - use interface instead)
/** @deprecated Use QueryRequest interface and createQueryRequest function instead */
export class QueryRequestClass {
  question: string;
  include_citations?: boolean;
  top_k?: number;

  constructor(question: string, include_citations?: boolean, top_k?: number) {
    this.question = question;
    this.include_citations = include_citations;
    this.top_k = top_k;
  }
}