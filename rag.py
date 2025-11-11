import os
# Correct Document import
from langchain_core.documents import Document
from langchain_ollama import OllamaLLM as Ollama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.schema.runnable import Runnable
from dotenv import load_dotenv



LLM_MODEL = "llama-2-7b"
EMBEDDING_MODEL = "text-embedding-3-small"
DOCUMENT_PATH = "/Users/melihkaan/Desktop/Courses/ENS491/document.doc"
VECTORSTORE_PATH = "/Users/melihkaan/Desktop/Courses/ENS491/vectorstore"

def create_model(model_name: str = LLM_MODEL) -> Ollama:
    """
    Creates an instance of the Ollama model.

    Args:
        model_name (str): The name of the Ollama model to use.

    Returns:
        Ollama: An instance of the Ollama model.
    """
    return Ollama(model=model_name)

def create_embedding_model(model_name: str = EMBEDDING_MODEL) -> OllamaEmbeddings:
    """
    Creates an instance of the OllamaEmbeddings model.

    Args:
        model_name (str): The name of the OllamaEmbeddings model to use.

    Returns:
        OllamaEmbeddings: An instance of the OllamaEmbeddings model.
    """
    return OllamaEmbeddings(model=model_name)

def load_directory(directory: str, glob_pattern: str = "*.txt") -> list[Document]:
    """
    Loads documents from a directory.
    Args:
        directory (str): The path to the directory containing documents.
        glob_pattern (str): The glob pattern to match files.

    Returns:
        list[Document]: A list of loaded documents.
    """
    loader = DirectoryLoader(directory, glob=glob_pattern, loader_cls=TextLoader)
    return loader.load()

def load_document(file_path: str) -> list[Document]:
    """
    Loads documents using the TextLoader.
    Args:
        file_path (str): The path to the document file.
    Returns:
        Document: The loaded document.
    """
    loader = TextLoader(file_path)
    return loader.load()

def create_splitter(chunk_size: int = 500, chunk_overlap: int = 50) -> RecursiveCharacterTextSplitter:
    """
    Creates an instance of the RecursiveCharacterTextSplitter.
    
    Args:
        chunk_size (int): The size of each chunk.
        chunk_overlap (int): The overlap between chunks.

    Returns:
        RecursiveCharacterTextSplitter: An instance of the text splitter.
    """
    # Using smaller chunks is often better for RAG
    return RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

def split_documents(documents: list[Document], splitter: RecursiveCharacterTextSplitter) -> list[Document]:
    """
    Splits documents into smaller chunks.
    
    Args:
        documents (list[Document]): The list of documents to split.
        splitter (RecursiveCharacterTextSplitter): The text splitter to use.
    
    Returns:
        list[Document]: The list of split documents.
    """
    return splitter.split_documents(documents)

def initialize_embedding_store(embedding_model: OllamaEmbeddings, documents: list[Document], persist_directory: str) -> Chroma:
    """
    Initializes a Chroma embedding store with the provided documents.
    Note: We pass the *split* documents here.
    """
    print("Embedding documents...")
    return Chroma.from_documents(
        documents=documents, 
        embedding=embedding_model,  # Corrected argument name
        persist_directory=persist_directory
    )

def create_retriever(embedding_store: Chroma, k: int = 4):
    """Creates a retriever from the provided embedding store."""
    return embedding_store.as_retriever(search_kwargs={"k": k})

def setup_rag_chain(llm: Ollama, retriever) -> Runnable:
    """
    Creates and returns the RAG retrieval chain.
    This function no longer runs the chat loop.
    """
    
    # This is the prompt template that LangChain expects
    # It must have 'context' and 'input' placeholders
    prompt_template_str = """
        Answer the following question based only on the provided context:

        <context>
        {context}
        </context>

        Question: {input}
    """
    
    prompt = ChatPromptTemplate.from_template(prompt_template_str)

    # This chain takes the LLM and the prompt template
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    
    # This chain combines the retriever and the QA chain
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    return rag_chain

def main():
    """Main function to run the RAG application."""
    
    # 1. Setup Models
    model = create_model(LLM_MODEL)
    embedding_model = create_embedding_model(EMBEDDING_MODEL)

    # 2. Load and Split Documents (Corrected Logic)
    print(f"Loading document: {DOCUMENT_PATH}")
    document = load_document(DOCUMENT_PATH)
    
    splitter = create_splitter()
    split_docs = split_documents(document, splitter)
    print(f"Split document into {len(split_docs)} chunks.")

    # 3. Initialize Vector Store (with split docs) 
    embedding_store = initialize_embedding_store(embedding_model, split_docs, VECTORSTORE_PATH)

    # 4. Create Retriever and RAG Chain
    retriever = create_retriever(embedding_store, k=4)
    rag_chain = setup_rag_chain(model, retriever)
    
    print("\n--- RAG Application with Chroma Ready ---")
    print("Ask a question about your document (type 'exit' to quit).")

    # 5. Run Interactive Chat Loop
    try:
        while True:
            question = input("\nYour question: ")
            if question.lower() in ['exit', 'quit']:
                break
            
            # Invoke the chain with the user's question
            response = rag_chain.invoke({"input": question})
            
            # Print the answer
            print("\nAnswer:", response["answer"])

    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()