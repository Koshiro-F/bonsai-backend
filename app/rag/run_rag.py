# create_vectorstore.py で作成した vectorstore を使用
import json
from typing import List

from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain.schema.messages import HumanMessage
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from myragas.myragas_eval import ragas_evaluation

load_dotenv(dotenv_path=".env.local")

TOP_K = 5

VECTORSTORE_PATH = "/root/workspace/data/vectorstore"
INFO_FILE_PATH = "/root/workspace/data/info/self_contained_info.jsonl"
# VALID_PDF_FILES = ["kouhou00137.pdf", "public_document_ministry02290.pdf"]
VALID_PDF_FILES = []


class RAGEvaluation:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
        )
        self.vectorstore = Chroma(
            embedding_function=self.embeddings, persist_directory=VECTORSTORE_PATH
        )
        self.documents = self.vectorstore.get()
        self.docs = self.documents["documents"]
        self.metadatas = self.documents["metadatas"]
        self.keyword_retriever = BM25Retriever.from_texts(
            self.documents["documents"],
            metadatas=self.documents["metadatas"],
            preprocess_func=self.preprocess_func,
        )
        self.vector_retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": TOP_K}
        )
        self.system_message = (
            "以下の社内文書に基づいて質問に対する厳密な回答を生成してください。"
        )
        self.llm = ChatOpenAI(model="gpt-4.1-mini")

        self.questions = []
        self.expected_answers = []
        self.model_outputs = []
        self.retrieved_texts = []

        self.data = []

    def main(self):
        # Load data from JSONL file
        with open(INFO_FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        data = json.loads(line)
                        question = data.get("original_question", "")
                        expected_answer = data.get("self_contained_answer", "")
                        if expected_answer == "":
                            expected_answer = data.get("answer", "")
                        pdf_name = data.get("pdf_name", "")

                        if len(VALID_PDF_FILES) > 0 and pdf_name not in VALID_PDF_FILES:
                            continue

                        if question and expected_answer:
                            print("file name", pdf_name)
                            print("question", question)
                            print("expected answer", expected_answer)
                            self.run(question=question, expected_answer=expected_answer)

                    except json.JSONDecodeError as e:
                        print(f"Error parsing JSON line: {e}")
                        continue
        result = ragas_evaluation(
            self.questions,
            self.expected_answers,
            self.model_outputs,
            self.retrieved_texts,
            output_file_name="ragas_result.csv",
        )
        print(result)

    def run_evaluation(
        self,
        question,
        expected_answer,
    ):
        """
        Update questions, model_outputs, expected_answers, retrieved_texts.

        Args:
            question (str): question
            expected_answer (str): expected answer

        Returns:
            None
        """
        result, metadata_list = self.generate_output(
            self.keyword_retriever, self.vector_retriever, question, self.system_message
        )
        self.questions.append(question)
        self.model_outputs.append(result)
        self.expected_answers.append(expected_answer)

    def preprocess_func(self, text: str) -> List[str]:
        i, j = 3, 5
        if len(text) < i:
            return [text]
        return self.generate_character_ngrams(text, i, j, True)

    def generate_character_ngrams(self, text, i, j, binary=False):
        """
        文字列から指定した文字数のn-f

        :param text: 文字列データ
        :param i: n-gramの最小文字数
        :param j: n-gramの最大文字数
        :param binary: Trueの場合、重複を削除
        :return: n-gramのリスト
        """
        ngrams = []

        for n in range(i, j + 1):
            for k in range(len(text) - n + 1):
                ngram = text[k : k + n]
                ngrams.append(ngram)

        if binary:
            ngrams = list(set(ngrams))  # 重複を削除

        return ngrams

    def generate_output(
        self, keyword_retriever, vector_retriever, user_input, system_message
    ):
        question = self.regenerate_question(user_input)
        keyword_searched = keyword_retriever.invoke(question)
        vector_searched = vector_retriever.invoke(question)
        texts_retrieved = []
        metadata_list = []
        for doc in vector_searched + keyword_searched:
            texts_retrieved.append(doc.page_content)
            metadata_list.append(doc.metadata)
        result = self.chat_based_on_texts(texts_retrieved, question, system_message)
        self.retrieved_texts.append(texts_retrieved)
        return result, metadata_list

    def regenerate_question(self, user_input):
        prompt = ChatPromptTemplate.from_template(
            """
            次の会話とフォローアップの質問を元に、フォローアップの質問を独立した質問として言い換えてください。
            ----------
            会話の履歴: {chat_history}
            ----------
            フォローアップの質問: {follow_up_question}
            ----------
            独立した質問:
            """
        )
        chain = prompt | self.llm
        follow_up_question = user_input
        # chat_history = st.session_state.messages
        chat_history = []
        args = {"chat_history": chat_history, "follow_up_question": follow_up_question}
        ans = chain.invoke(args)
        return str(ans.content)

    def chat_based_on_texts(self, texts_retrieved, question, system_message):
        texts = "\n\n".join(texts_retrieved)
        prompt_text = f"""
            {system_message}
            ----------
            会話記録を元にユーザーとの会話のキャッチボールを成立させてください。
            ----------
            会話記録{[]}
            ----------
            社内文書: {texts}
            ----------
            質問: {question}
            """

        return self.llm.invoke(
            [HumanMessage(content=[{"type": "text", "text": prompt_text}])]
        ).content


if __name__ == "__main__":
    rag = RAGEvaluation()

    rag.main()
