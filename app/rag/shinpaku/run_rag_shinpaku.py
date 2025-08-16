# 真柏データベースを使用したインタラクティブAIチャット
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
BACKEND_ROOT = os.path.join(SCRIPT_DIR, "..", "..", "..")
ENV_PATH = os.path.join(BACKEND_ROOT, ".env.local")

load_dotenv(dotenv_path=ENV_PATH)

TOP_K = 5  # 最終的な検索結果数
BM25_K = 3  # BM25検索の取得数
VECTOR_K = 3  # ベクトル検索の取得数

VECTORSTORE_PATH = os.path.join(BACKEND_ROOT, "data", "vectorstore_shinpaku")

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


class RAGChatBotShinpaku:
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
        
        # システムメッセージ
        self.system_message = (
            """あなたは盆栽の専門家です。以下に与えられた盆栽の専門文書のデータに基づいて、ユーザーの質問に対して回答を生成してください。
            
            【回答方針】
            ・盆栽の専門用語や技法について正確に説明してください
            ・専門文書に基づく回答を優先し、不正確な部分があれば断定は避けてください
            ・推測に基づく回答をする場合は、その旨を明確に伝えてください
            ・実践的なアドバイスを求められた場合は、安全性にも配慮してください
            
            【注意点】
            ・専門文書のデータは盆栽雑誌から読み取ったものであるため、文章の構造が不自然な場合があります。
            ・出力はできるだけ平文で行い、markdown形式は避けてください。"""
        )
        
        self.model = "gpt-4.1-nano"
        self.llm = ChatOpenAI(model=self.model)
        
        # 会話履歴を保持
        self.chat_history = []
        self.show_content = show_content
        
        # トークン追跡機能
        self.track_tokens = track_tokens
        self.token_tracker = TokenTracker() if track_tokens else None
        
        print("チャットボットの準備が完了しました！")
        if track_tokens:
            print("💰 トークン使用量追跡: 有効")
        
        # データベース統計情報を表示
        self.display_database_stats()

    def display_database_stats(self):
        """データベースの統計情報を表示"""
        if not self.metadatas:
            return
        
        print("\n" + "=" * 60)
        print("📊 データベース統計情報")
        print("=" * 60)
        
        total_docs = len(self.metadatas)
        print(f"総ドキュメント数: {total_docs}")
        
        # 文献名の統計
        文献名_set = set()
        樹種_set = set()
        章_set = set()
        
        for metadata in self.metadatas:
            if metadata.get('文献名'):
                文献名_set.add(metadata['文献名'])
            if metadata.get('樹種') and metadata['樹種'].strip():
                樹種_set.add(metadata['樹種'])
            if metadata.get('章') and metadata['章'].strip():
                章_set.add(metadata['章'])
        
        print(f"文献数: {len(文献名_set)}")
        print(f"樹種数: {len(樹種_set)}")
        print(f"章数: {len(章_set)}")
        
        if 樹種_set:
            print(f"\n主な樹種: {', '.join(sorted(list(樹種_set))[:10])}")
        
        print("=" * 60)

    def main(self):
        print("=" * 60)
        print("真柏・盆栽専用AIチャットボット")
        print("=" * 60)
        print("真柏や盆栽に関する質問を入力してください。")
        print("終了するには 'quit', 'exit', 'q' を入力してください。")
        print("履歴をクリアするには 'clear' を入力してください。")
        if self.track_tokens:
            print("トークン使用量を確認するには 'tokens' を入力してください。")
        print("-" * 60)
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
                
                print("\n🔍 検索中...")
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

    def run_chat(self, question: str) -> Tuple[str, list, list]:
        """
        ユーザーの質問に対してRAGを使用して回答を生成する
        
        Args:
            question (str): ユーザーの質問
            
        Returns:
            Tuple[str, list, list]: 生成された回答、メタデータ、参照ドキュメント
        """
        result, metadata_list, referenced_docs = self.generate_output(
            self.keyword_retriever, 
            self.vector_retriever, 
            question, 
            self.system_message
        )
        return result, metadata_list, referenced_docs

    def preprocess_func(self, text: str) -> List[str]:
        """BM25用の前処理関数"""
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
        """RAG検索と回答生成"""
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
            盆栽に関する専門的な文脈を考慮してください。
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
            self.token_tracker.track_usage(self.model, estimated_input_tokens, output_tokens)
            print(f"    {self.token_tracker.get_query_summary(self.model, estimated_input_tokens, output_tokens)}")
            
        return str(ans.content)

    def chat_based_on_texts(self, texts_retrieved, question, system_message):
        """検索結果を基にした回答生成"""
        texts = "\n\n".join(texts_retrieved)
        
        # 会話履歴を文字列形式に変換
        history_str = ""
        for msg in self.chat_history[-4:]:  # 最新の4つの発言のみ使用
            history_str += f"{msg['role']}: {msg['content']}\n"
        
        prompt_text = f"""
            {system_message}
            ----------
            会話記録を元にユーザーとの会話のキャッチボールを成立させてください。
            盆栽の専門知識を正確に伝え、実践的なアドバイスを提供してください。
            ----------
            会話記録: {history_str}
            ----------
            専門文書からの参考情報: {texts}
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
            self.token_tracker.track_usage(self.model, estimated_input_tokens, output_tokens)
            print(f"    {self.token_tracker.get_query_summary(self.model, estimated_input_tokens, output_tokens)}")
            
        return response.content

    def display_referenced_documents(self, metadata_list, referenced_docs, show_content=False):
        """
        参照したドキュメントの情報を整理して表示する（整備済みデータ用にカスタマイズ）
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
            文献名 = metadata.get('文献名', '不明な文献')
            ページ = metadata.get('ページ', '不明なページ')
            章 = metadata.get('章', '')
            節 = metadata.get('節', '')
            樹種 = metadata.get('樹種', '')
            区分 = metadata.get('区分', '')
            row_number = metadata.get('row_number', '')
            
            # キーの作成（文献名とページで識別）
            key = f"{文献名}_page_{ページ}"
            
            if key not in doc_info:
                doc_info[key] = {
                    '文献名': 文献名,
                    'ページ': ページ,
                    '章': 章,
                    '節': 節,
                    '樹種': set(),
                    '区分': set(),
                    'contents': set()  # 重複を避けるためsetを使用
                }
            
            # 樹種と区分の情報を追加
            if 樹種 and 樹種.strip():
                doc_info[key]['樹種'].add(樹種)
            if 区分 and 区分.strip():
                doc_info[key]['区分'].add(区分)
                
            # RAGで参照したチャンクのテキストを取得
            if show_content:
                doc_info[key]['contents'].add(doc.page_content)

        if doc_info:
            print("\n" + "=" * 60)
            print("📚 参照したデータ:")
            print("=" * 60)
            
            # 文献名とページでソート
            sorted_docs = sorted(doc_info.values(), key=lambda x: (x['文献名'], str(x['ページ'])))
            
            for doc in sorted_docs:
                # 基本情報の表示
                info_parts = [f"📄 {doc['文献名']}"]
                if doc['ページ']:
                    info_parts.append(f"ページ {doc['ページ']}")
                
                print(f"\n{' '.join(info_parts)}")
                
                # 詳細情報の表示
                details = []
                if doc['章']:
                    details.append(f"章: {doc['章']}")
                if doc['節']:
                    details.append(f"節: {doc['節']}")
                if doc['樹種']:
                    樹種_str = ", ".join(sorted(doc['樹種']))
                    details.append(f"樹種: {樹種_str}")
                if doc['区分']:
                    区分_str = ", ".join(sorted(doc['区分']))
                    details.append(f"区分: {区分_str}")
                
                if details:
                    print(f"  {' | '.join(details)}")
                
                # コンテンツの表示
                if show_content and doc['contents']:
                    print("  📝 参照内容:")
                    for idx, content in enumerate(sorted(doc['contents'])):  # 順序を一定に
                        print(f"    [{idx+1}] {content[:300]}{'...' if len(content)>300 else ''}")
                        if idx < len(doc['contents']) - 1:
                            print("    " + "-" * 50)
            
            print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='盆栽専用RAGチャットボット')
    parser.add_argument('--show-content', action='store_true', 
                       help='参照ドキュメントの内容も表示する')
    parser.add_argument('--track-tokens', action='store_true', default=True, 
                       help='トークン使用量を追跡する（デフォルト: 有効）')
    parser.add_argument('--no-track-tokens', action='store_true', 
                       help='トークン使用量追跡を無効にする')
    args = parser.parse_args()
    
    # トークン追跡の設定
    track_tokens = args.track_tokens and not args.no_track_tokens
    
    try:
        chatbot = RAGChatBotShinpaku(show_content=args.show_content, track_tokens=track_tokens)
        chatbot.main()
    except Exception as e:
        print(f"初期化エラー: {e}")
        print("整備済みデータのベクトルストアが存在することを確認してください。")
        print("先に create_vectorstore_shinpaku.py を実行してください。")
