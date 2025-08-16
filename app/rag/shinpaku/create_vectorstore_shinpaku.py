import os
import time
import warnings
import pandas as pd
from typing import List, Dict

from dotenv import load_dotenv
from langchain.schema.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# スクリプトファイルの位置を基準にパスを計算（カレントディレクトリに依存しない）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.join(SCRIPT_DIR, "..", "..", "..")
ENV_PATH = os.path.join(BACKEND_ROOT, ".env.local")

load_dotenv(dotenv_path=ENV_PATH)

# パス設定
CSV_FILE_PATH = os.path.join(BACKEND_ROOT, "data", "input_shinpaku", "shinpaku_data.csv")
VECTORSTORE_PATH = os.path.join(BACKEND_ROOT, "data", "vectorstore_shinpaku")
PROCESSED_FILES_TXT = os.path.join(BACKEND_ROOT, "data", "processed_shinpaku_files.txt")


class CreateVectorstoreShinpaku:
    def __init__(self):
        """
        真柏データ用のベクトルストア作成クラス
        """
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
        )
        
        if os.path.exists(VECTORSTORE_PATH):
            print("--------------------------------")
            warnings.warn("vectorstore already exists, you may want to delete it")
            print("vectorstore will not be overwritten, adding new documents")
            print("--------------------------------")
        
        self.vectorstore = Chroma(
            embedding_function=self.embeddings, 
            persist_directory=VECTORSTORE_PATH
        )
        
        # CSVデータ用のチャンクサイズを調整
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512, 
            chunk_overlap=128
        )

    def main(self):
        """
        メイン処理：CSVファイルを読み込み、ベクトルストアを作成
        """
        print("真柏データCSVファイルの処理を開始します...")
        
        # 処理済みファイルの確認
        if os.path.exists(PROCESSED_FILES_TXT):
            with open(PROCESSED_FILES_TXT, "r", encoding="utf-8") as f:
                processed_files = set(f.read().splitlines())
        else:
            processed_files = set()
        
        csv_filename = os.path.basename(CSV_FILE_PATH)
        
        if csv_filename not in processed_files:
            print(f"処理中: {csv_filename}")
            
            # CSVファイルの読み込み
            documents = self.process_csv_file()
            print(f"CSVから {len(documents)} 件のドキュメントを作成しました")
            
            # ベクトルストアに追加
            self.add_documents_to_vectorstore(documents)
            print("ベクトルストアへの追加が完了しました")
            
            # 処理済みファイルとして記録
            processed_files.add(csv_filename)
            with open(PROCESSED_FILES_TXT, "w", encoding="utf-8") as f:
                f.write("\n".join(processed_files))
            
            # ベクトルストアの永続化
            self.vectorstore.persist()
            print("ベクトルストアの永続化が完了しました")
        else:
            print(f"{csv_filename} は既に処理済みです")

    def process_csv_file(self) -> List[Document]:
        """
        CSVファイルを読み込み、Documentオブジェクトのリストを作成
        
        Returns:
            List[Document]: 作成されたドキュメントのリスト
        """
        try:
            # CSVファイルの読み込み
            df = pd.read_csv(CSV_FILE_PATH, encoding="utf-8")
            print(f"CSVファイル読み込み完了: {len(df)} 行")
            
            documents = []
            
            for index, row in df.iterrows():
                # 内容フィールドが空でない場合のみ処理
                content = str(row['内容']).strip()
                if content and content != 'nan' and len(content) > 10:
                    
                    # メタデータの作成
                    metadata = {
                        "source": "shinpaku_data.csv",
                        "filename": "shinpaku_data.csv",
                        "row_number": index + 2,  # ヘッダー行を考慮（1-based）
                        "文献名": str(row['文献名']) if pd.notna(row['文献名']) else "",
                        "ページ": str(row['ページ']) if pd.notna(row['ページ']) else "",
                        "章": str(row['章']) if pd.notna(row['章']) else "",
                        "節": str(row['節']) if pd.notna(row['節']) else "",
                        "区分": str(row['区分']) if pd.notna(row['区分']) else "",
                        "樹種": str(row['樹種']) if pd.notna(row['樹種']) else "",
                        "type": "text"
                    }
                    
                    # チャンクに分割
                    chunks = self.text_splitter.split_text(content)
                    
                    # 各チャンクに対してDocumentオブジェクトを作成
                    for chunk_index, chunk in enumerate(chunks):
                        if len(chunk.strip()) > 3:  # 短すぎるチャンクは除外
                            chunk_metadata = metadata.copy()
                            chunk_metadata["chunk_index"] = chunk_index
                            
                            # メタデータをテキストに統合（検索対象に含める）
                            enhanced_content = self.create_enhanced_content(chunk, row)
                            
                            doc = Document(
                                page_content=enhanced_content,
                                metadata=chunk_metadata
                            )
                            documents.append(doc)
            
            return documents
            
        except Exception as e:
            print(f"CSVファイル処理中にエラーが発生しました: {e}")
            raise

    def add_documents_to_vectorstore(self, documents: List[Document]):
        """
        ドキュメントをベクトルストアに追加
        
        Args:
            documents (List[Document]): 追加するドキュメントのリスト
        """
        if not documents:
            print("追加するドキュメントがありません")
            return
        
        print(f"{len(documents)} 個のドキュメントをベクトルストアに追加中...")
        
        # バッチサイズを設定してメモリ使用量を制御
        batch_size = 100
        total_batches = (len(documents) + batch_size - 1) // batch_size
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            print(f"バッチ {batch_num}/{total_batches} を処理中... ({len(batch)} ドキュメント)")
            
            try:
                self.vectorstore.add_documents(batch)
            except Exception as e:
                print(f"バッチ {batch_num} の処理中にエラーが発生しました: {e}")
                raise

    def get_statistics(self) -> Dict:
        """
        作成されたベクトルストアの統計情報を取得
        
        Returns:
            Dict: 統計情報
        """
        try:
            data = self.vectorstore.get()
            total_docs = len(data['documents'])
            
            # メタデータから統計情報を抽出
            metadatas = data['metadatas']
            文献名_set = set()
            樹種_set = set()
            
            for metadata in metadatas:
                if metadata.get('文献名'):
                    文献名_set.add(metadata['文献名'])
                if metadata.get('樹種'):
                    樹種_set.add(metadata['樹種'])
            
            return {
                "total_documents": total_docs,
                "unique_文献名": len(文献名_set),
                "unique_樹種": len(樹種_set),
                "文献名_list": sorted(list(文献名_set)),
                "樹種_list": sorted(list(樹種_set))
            }
        except Exception as e:
            print(f"統計情報取得中にエラーが発生しました: {e}")
            return {}

    def create_enhanced_content(self, content: str, row) -> str:
        """
        内容にメタデータ情報を統合して検索対象を拡張
        
        Args:
            content (str): 元の内容テキスト
            row: CSVの行データ
            
        Returns:
            str: メタデータ統合済みのテキスト
        """
        metadata_parts = []
        
        # 有効なメタデータのみを追加
        if pd.notna(row['樹種']) and str(row['樹種']).strip():
            metadata_parts.append(f"樹種: {str(row['樹種'])}")
        
        if pd.notna(row['章']) and str(row['章']).strip():
            metadata_parts.append(f"章: {str(row['章'])}")
        
        if pd.notna(row['節']) and str(row['節']).strip():
            metadata_parts.append(f"節: {str(row['節'])}")
        
        if pd.notna(row['区分']) and str(row['区分']).strip():
            metadata_parts.append(f"区分: {str(row['区分'])}")
        
        # メタデータがある場合は先頭に追加
        if metadata_parts:
            enhanced_content = "\n".join(metadata_parts) + "\n\n" + content
        else:
            enhanced_content = content
        
        return enhanced_content


if __name__ == "__main__":
    start_time = time.time()
    
    print("=" * 60)
    print("真柏データベクトルストア作成スクリプト")
    print("=" * 60)
    
    try:
        cv = CreateVectorstoreShinpaku()
        cv.main()
        
        # 統計情報の表示
        stats = cv.get_statistics()
        if stats:
            print("\n" + "=" * 60)
            print("作成完了 - 統計情報:")
            print("=" * 60)
            print(f"総ドキュメント数: {stats['total_documents']}")
            print(f"文献数: {stats['unique_文献名']}")
            print(f"樹種数: {stats['unique_樹種']}")
            
            if stats['文献名_list']:
                print(f"\n文献名:")
                for 文献 in stats['文献名_list'][:10]:  # 最初の10個のみ表示
                    print(f"  - {文献}")
                if len(stats['文献名_list']) > 10:
                    print(f"  ... 他 {len(stats['文献名_list']) - 10} 件")
            
            if stats['樹種_list']:
                print(f"\n樹種:")
                for 樹種 in stats['樹種_list']:
                    if 樹種:  # 空文字でない場合のみ
                        print(f"  - {樹種}")
        
        end_time = time.time()
        print(f"\n処理時間: {(end_time - start_time):.2f} 秒")
        print("=" * 60)
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
