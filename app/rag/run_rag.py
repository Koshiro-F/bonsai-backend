# ベクトルストアを使用したインタラクティブAIチャット
import json
from typing import List, Tuple

from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain.schema.messages import HumanMessage
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv(dotenv_path="/home/fujikawa/jinshari/flask-bonsai/.env.local")

TOP_K = 5

VECTORSTORE_PATH = "/home/fujikawa/jinshari/flask-bonsai/data/vectorstore"


class RAGChatBot:
    def __init__(self, show_content=False):
        print("ベクトルストアを読み込み中...")
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
        )
        self.vectorstore = Chroma(
            embedding_function=self.embeddings, persist_directory=VECTORSTORE_PATH
        )
        self.documents = self.vectorstore.get()
        self.docs = self.documents["documents"]
        self.metadatas = self.documents["metadatas"]
        
        print("BM25リトリーバーを初期化中...")
        self.keyword_retriever = BM25Retriever.from_texts(
            self.documents["documents"],
            metadatas=self.documents["metadatas"],
            preprocess_func=self.preprocess_func,
        )
        self.vector_retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": TOP_K}
        )
        self.system_message = (
            """あなたは盆栽の専門家です。以下に与えられた盆栽の専門文書のデータに基づいて、ユーザーの質問に対して回答を生成してください。
            なるべく専門文書のデータに基づいて回答するようにし、不正確な部分があれば断定は避けてください。
            推測に基づく回答をする場合は、その旨を伝えてください。"""
        )
        self.llm = ChatOpenAI(model="gpt-4.1-nano")
        
        # 会話履歴を保持
        self.chat_history = []
        self.show_content = show_content
        
        print("チャットボットの準備が完了しました！")

    def main(self):
        print("=" * 50)
        print("ベクトルストアベースAIチャットボット")
        print("=" * 50)
        print("質問を入力してください。終了するには 'quit', 'exit', 'q' を入力してください。")
        print("履歴をクリアするには 'clear' を入力してください。")
        print("-" * 50)
        print("参照ドキュメントの内容も表示する: {}".format("ON" if self.show_content else "OFF"))
        
        while True:
            try:
                user_input = input("\nあなた: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("チャットを終了します。")
                    break
                elif user_input.lower() == 'clear':
                    self.chat_history = []
                    print("会話履歴をクリアしました。")
                    continue
                elif not user_input:
                    print("質問を入力してください。")
                    continue
                
                print("\n検索中...")
                response, metadata_list, referenced_docs = self.run_chat(user_input)
                print(f"\nAI: {response}")
                
                # 参照したドキュメント情報を表示
                self.display_referenced_documents(metadata_list, referenced_docs, show_content=self.show_content)
                
                # 会話履歴に追加
                self.chat_history.append({"role": "user", "content": user_input})
                self.chat_history.append({"role": "assistant", "content": response})
                
                # 会話履歴が長くなりすぎた場合は古いものを削除
                if len(self.chat_history) > 10:
                    self.chat_history = self.chat_history[-10:]
                    
            except KeyboardInterrupt:
                print("\n\nチャットを終了します。")
                break
            except Exception as e:
                print(f"\nエラーが発生しました: {e}")
                continue

    def run_chat(self, question: str) -> Tuple[str, list]:
        """
        ユーザーの質問に対してRAGを使用して回答を生成する
        
        Args:
            question (str): ユーザーの質問
            
        Returns:
            Tuple[str, list]: 生成された回答と参照したドキュメントのメタデータ
        """
        result, metadata_list, referenced_docs = self.generate_output(
            self.keyword_retriever, 
            self.vector_retriever, 
            question, 
            self.system_message
        )
        return result, metadata_list, referenced_docs

    def preprocess_func(self, text: str) -> List[str]:
        i, j = 3, 5
        if len(text) < i:
            return [text]
        return self.generate_character_ngrams(text, i, j, True)

    def generate_character_ngrams(self, text, i, j, binary=False):
        """
        文字列から指定した文字数のn-gramを生成
        
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
        referenced_docs = []  # 参照したドキュメントを保持
        for doc in vector_searched + keyword_searched:
            texts_retrieved.append(doc.page_content)
            metadata_list.append(doc.metadata)
            referenced_docs.append(doc)  # Document オブジェクトを保持
        result = self.chat_based_on_texts(texts_retrieved, question, system_message)
        return result, metadata_list, referenced_docs  # referenced_docsも返す

    def regenerate_question(self, user_input):
        """
        会話履歴を考慮して質問を再生成する
        """
        if not self.chat_history:
            return user_input
            
        prompt = ChatPromptTemplate.from_template(
            """
            次の会話履歴とフォローアップの質問を元に、フォローアップの質問を独立した質問として言い換えてください。
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
        args = {"chat_history": self.chat_history, "follow_up_question": follow_up_question}
        ans = chain.invoke(args)
        return str(ans.content)

    def chat_based_on_texts(self, texts_retrieved, question, system_message):
        texts = "\n\n".join(texts_retrieved)
        
        # 会話履歴を文字列形式に変換
        history_str = ""
        for msg in self.chat_history[-4:]:  # 最新の4つの発言のみ使用
            history_str += f"{msg['role']}: {msg['content']}\n"
        
        prompt_text = f"""
            {system_message}
            ----------
            会話記録を元にユーザーとの会話のキャッチボールを成立させてください。
            ----------
            会話記録: {history_str}
            ----------
            専門文書: {texts}
            ----------
            質問: {question}
            """

        return self.llm.invoke(
            [HumanMessage(content=[{"type": "text", "text": prompt_text}])]
        ).content

    def display_referenced_documents(self, metadata_list, referenced_docs, show_content=False):
        """
        参照したドキュメントの情報を整理して表示する
        Args:
            metadata_list (list): ドキュメントのメタデータリスト
            referenced_docs (list): 参照したドキュメントのリスト
            show_content (bool): テキスト内容も表示するか
        """
        if not metadata_list:
            return
        doc_info = {}
        # metadataとdocsを対応付けて処理
        for i, (metadata, doc) in enumerate(zip(metadata_list, referenced_docs)):
            filename = metadata.get('filename', '不明なファイル')
            page_number = metadata.get('page_number', '不明なページ')
            doc_type = metadata.get('type', 'Text')
            key = f"{filename}_page_{page_number}"
            if key not in doc_info:
                doc_info[key] = {
                    'filename': filename,
                    'page_number': page_number,
                    'types': set(),
                    'contents': set()  # 重複を避けるためsetを使用
                }
            doc_info[key]['types'].add(doc_type)
            # RAGで参照したチャンクのテキストを取得
            if show_content:
                doc_info[key]['contents'].add(doc.page_content)

        if doc_info:
            print("\n" + "=" * 50)
            print("📚 参照したドキュメント:")
            print("=" * 50)
            sorted_docs = sorted(doc_info.values(), key=lambda x: (x['filename'], x['page_number']))
            for doc in sorted_docs:
                types_str = ", ".join(sorted(doc['types']))
                print(f"\n📄 {doc['filename']} (ページ {doc['page_number']}) - {types_str}")
                if show_content and doc['contents']:
                    for idx, content in enumerate(sorted(doc['contents'])):  # 順序を一定に
                        print(f"  [内容{idx+1}]:")
                        print(f"  {content[:500]}{'...' if len(content)>500 else ''}")
                        print("-" * 40)
            print("=" * 50)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--show-content', action='store_true', help='参照ドキュメントの内容も表示する')
    args = parser.parse_args()
    try:
        chatbot = RAGChatBot(show_content=args.show_content)
        chatbot.main()
    except Exception as e:
        print(f"初期化エラー: {e}")
        print("ベクトルストアが存在することを確認してください。")
