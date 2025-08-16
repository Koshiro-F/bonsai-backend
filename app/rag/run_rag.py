# ベクトルストアを使用したインタラクティブAIチャット
import json
import os
import time
from typing import List, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
from langchain.schema.messages import HumanMessage
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# スクリプトファイルの位置を基準にパスを計算（カレントディレクトリに依存しない）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.join(SCRIPT_DIR, "..", "..")
ENV_PATH = os.path.join(BACKEND_ROOT, ".env.local")

load_dotenv(dotenv_path=ENV_PATH)

TOP_K = 3
BM25_K = 2  # BM25検索の取得数
VECTOR_K = 2  # ベクトル検索の取得数

VECTORSTORE_PATH = os.path.join(BACKEND_ROOT, "data", "vectorstore_page_unified")

# OpenAI API料金設定（2024年1月現在）
PRICING = {
    "gpt-4o": {"input": 0.00250, "output": 0.01000},  # per 1K tokens
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},  # per 1K tokens
    "gpt-4.1-nano": {"input": 0.0001, "output": 0.00040},  # gpt-4o-miniと同等と仮定
    "text-embedding-ada-002": {"input": 0.00010, "output": 0.0}  # per 1K tokens
}

@dataclass
class TokenUsage:
    """トークン使用量を追跡するクラス"""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    
    def add_usage(self, input_tokens: int, output_tokens: int = 0):
        """使用量を追加し、コストを計算"""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        
        if self.model in PRICING:
            pricing = PRICING[self.model]
            self.cost = (self.input_tokens * pricing["input"] + 
                        self.output_tokens * pricing["output"]) / 1000
    
    def __str__(self):
        return f"{self.model}: {self.input_tokens}in + {self.output_tokens}out = ${self.cost:.6f}"

class TokenTracker:
    """API使用量を追跡するクラス"""
    def __init__(self):
        self.session_usage = {}
        self.total_usage = {}
        self.start_time = time.time()
    
    def track_usage(self, model: str, input_tokens: int, output_tokens: int = 0):
        """使用量を記録"""
        if model not in self.session_usage:
            self.session_usage[model] = TokenUsage(model)
            self.total_usage[model] = TokenUsage(model)
        
        self.session_usage[model].add_usage(input_tokens, output_tokens)
        self.total_usage[model].add_usage(input_tokens, output_tokens)
    
    def get_session_summary(self) -> str:
        """セッション全体の使用量サマリーを取得"""
        if not self.session_usage:
            return "📊 トークン使用量: なし"
        
        summary = ["📊 セッション使用量:"]
        total_cost = 0.0
        
        for model, usage in self.session_usage.items():
            summary.append(f"  {usage}")
            total_cost += usage.cost
        
        duration = time.time() - self.start_time
        summary.append(f"  合計コスト: ${total_cost:.6f}")
        summary.append(f"  セッション時間: {duration:.1f}秒")
        
        return "\n".join(summary)
    
    def get_query_summary(self, model: str, input_tokens: int, output_tokens: int = 0) -> str:
        """クエリ単位の使用量サマリーを取得"""
        if model in PRICING:
            pricing = PRICING[model]
            cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000
            return f"💰 {model}: {input_tokens}in + {output_tokens}out = ${cost:.6f}"
        return f"💰 {model}: {input_tokens}in + {output_tokens}out"


class RAGChatBot:
    def __init__(self, show_content=False, track_tokens=True):
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
            k=BM25_K  # BM25検索の結果数を明示的に指定
        )
        self.vector_retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": VECTOR_K}  # ベクトル検索の結果数を指定
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
        
        # トークン追跡機能
        self.track_tokens = track_tokens
        self.token_tracker = TokenTracker() if track_tokens else None
        
        print("チャットボットの準備が完了しました！")
        if track_tokens:
            print("💰 トークン使用量追跡: 有効")

    def main(self):
        print("=" * 50)
        print("ベクトルストアベースAIチャットボット")
        print("=" * 50)
        print("質問を入力してください。終了するには 'quit', 'exit', 'q' を入力してください。")
        print("履歴をクリアするには 'clear' を入力してください。")
        if self.track_tokens:
            print("トークン使用量を確認するには 'tokens' を入力してください。")
        print("-" * 50)
        print("参照ドキュメントの内容も表示する: {}".format("ON" if self.show_content else "OFF"))
        if self.track_tokens:
            print("トークン使用量追跡: ON")
        
        while True:
            try:
                user_input = input("\nあなた: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    if self.track_tokens and self.token_tracker:
                        print("\n" + self.token_tracker.get_session_summary())
                    print("チャットを終了します。")
                    break
                elif user_input.lower() == 'clear':
                    self.chat_history = []
                    print("会話履歴をクリアしました。")
                    continue
                elif user_input.lower() == 'tokens' and self.track_tokens:
                    if self.token_tracker:
                        print("\n" + self.token_tracker.get_session_summary())
                    else:
                        print("トークン追跡が無効です。")
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
        
        # ベクトル検索でのembedding使用量を追跡
        if self.track_tokens and self.token_tracker:
            # クエリのembedding作成コスト
            query_tokens = len(question) // 4  # 大まかな推定
            self.token_tracker.track_usage("text-embedding-ada-002", query_tokens, 0)
            print(f"    {self.token_tracker.get_query_summary('text-embedding-ada-002', query_tokens, 0)}")
        
        vector_searched = vector_retriever.invoke(question)
        
        # 重複除去とTOP_K個への制限
        unique_docs = []
        seen_contents = set()
        
        # ベクトル検索結果を優先して追加
        for doc in vector_searched:
            content_hash = hash(doc.page_content)
            if content_hash not in seen_contents and len(unique_docs) < TOP_K:
                unique_docs.append(doc)
                seen_contents.add(content_hash)
        
        # 残りの枠をBM25検索結果で埋める
        for doc in keyword_searched:
            content_hash = hash(doc.page_content)
            if content_hash not in seen_contents and len(unique_docs) < TOP_K:
                unique_docs.append(doc)
                seen_contents.add(content_hash)
        
        # 最終的にTOP_K個に制限
        final_docs = unique_docs[:TOP_K]
        
        texts_retrieved = []
        metadata_list = []
        referenced_docs = []
        
        for doc in final_docs:
            texts_retrieved.append(doc.page_content)
            metadata_list.append(doc.metadata)
            referenced_docs.append(doc)
        
        print(f"🔍 検索結果: ベクトル{len(vector_searched)}件 + BM25 {len(keyword_searched)}件 → 重複除去後{len(final_docs)}件")
        
        result = self.chat_based_on_texts(texts_retrieved, question, system_message)
        return result, metadata_list, referenced_docs

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
        
        # トークン使用量を追跡
        if self.track_tokens and self.token_tracker:
            # 入力トークンの概算（正確には取得困難なので推定）
            input_text = str(self.chat_history) + follow_up_question
            estimated_input_tokens = len(input_text) // 4  # 大まかな推定
            
        ans = chain.invoke(args)
        
        # トークン使用量を記録（推定値）
        if self.track_tokens and self.token_tracker:
            output_tokens = len(str(ans.content)) // 4  # 大まかな推定
            self.token_tracker.track_usage("gpt-4.1-nano", estimated_input_tokens, output_tokens)
            print(f"    {self.token_tracker.get_query_summary('gpt-4.1-nano', estimated_input_tokens, output_tokens)}")
            
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

        # トークン使用量を追跡
        if self.track_tokens and self.token_tracker:
            # 入力トークンの概算
            estimated_input_tokens = len(prompt_text) // 4  # 大まかな推定
            
        response = self.llm.invoke(
            [HumanMessage(content=[{"type": "text", "text": prompt_text}])]
        )
        
        # トークン使用量を記録
        if self.track_tokens and self.token_tracker:
            output_tokens = len(response.content) // 4  # 大まかな推定
            self.token_tracker.track_usage("gpt-4.1-nano", estimated_input_tokens, output_tokens)
            print(f"    {self.token_tracker.get_query_summary('gpt-4.1-nano', estimated_input_tokens, output_tokens)}")
            
        return response.content

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
            # ページ統合型処理に対応
            if metadata.get('processing_type') == 'page_unified':
                filename = metadata.get('title', '不明なファイル')
                page_number = metadata.get('page_number', '不明なページ')
                doc_type = metadata.get('content_type', 'page_unified')
            else:
                # 従来の処理との互換性
                filename = metadata.get('filename', '不明なファイル')
                page_number = metadata.get('page_number', '不明なページ')
                doc_type = metadata.get('type', 'Text')
            
            key = f"{filename}_page_{page_number}"
            if key not in doc_info:
                doc_info[key] = {
                    'filename': filename,
                    'page_number': page_number,
                    'types': set(),
                    'contents': set(),  # 重複を避けるためsetを使用
                    'theme': metadata.get('theme', ''),  # ページ統合型のテーマ情報
                    'processing_type': metadata.get('processing_type', 'legacy')
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
                
                # ページ統合型処理の追加情報を表示
                if doc['processing_type'] == 'page_unified':
                    theme_info = f" | テーマ: {doc['theme']}" if doc['theme'] else ""
                    print(f"\n📄 {doc['filename']} (ページ {doc['page_number']}) - {types_str}{theme_info}")
                else:
                    print(f"\n📄 {doc['filename']} (ページ {doc['page_number']}) - {types_str}")
                
                if show_content and doc['contents']:
                    for idx, content in enumerate(sorted(doc['contents'])):  # 順序を一定に
                        print(f"  [内容{idx+1}]:")
                        # ページ統合型の場合は少し多めに表示
                        content_limit = 800 if doc['processing_type'] == 'page_unified' else 500
                        print(f"  {content[:content_limit]}{'...' if len(content)>content_limit else ''}")
                        print("-" * 40)
            print("=" * 50)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--show-content', action='store_true', help='参照ドキュメントの内容も表示する')
    parser.add_argument('--track-tokens', action='store_true', default=True, help='トークン使用量を追跡する（デフォルト: 有効）')
    parser.add_argument('--no-track-tokens', action='store_true', help='トークン使用量追跡を無効にする')
    args = parser.parse_args()
    
    # トークン追跡の設定
    track_tokens = args.track_tokens and not args.no_track_tokens
    
    try:
        chatbot = RAGChatBot(show_content=args.show_content, track_tokens=track_tokens)
        chatbot.main()
    except Exception as e:
        print(f"初期化エラー: {e}")
        print("ベクトルストアが存在することを確認してください。")
