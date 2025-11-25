export class QueryRequest {
    question: string;
    include_citations?: boolean;
    top_k?: number;

    constructor(question: string, include_citations?: boolean, top_k?: number) {
        this.question = question;
        this.include_citations = include_citations;
        this.top_k = top_k;
    }
}