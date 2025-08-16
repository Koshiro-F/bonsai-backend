"""
真柏RAG API用サービスクラス

Web API用にRAGChatBotShinpakuをラップし、
セッション管理やエラーハンドリングを提供
"""

import time
import traceback
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from .run_rag_shinpaku import RAGChatBotShinpaku


class RAGApiService:
    """RAG API用サービスクラス"""
    
    def __init__(self):
        """サービス初期化"""
        self.rag_bot = None
        self.sessions = {}  # セッション管理用辞書
        self.initialized = False
        self.initialization_error = None
        
    def initialize(self) -> bool:
        """RAGボットの初期化"""
        if self.initialized:
            return True
            
        try:
            print("🤖 RAGボットを初期化中...")
            self.rag_bot = RAGChatBotShinpaku(show_content=False, track_tokens=True)
            self.initialized = True
            print("✅ RAGボット初期化完了")
            return True
        except Exception as e:
            error_msg = f"RAGボット初期化エラー: {str(e)}"
            print(f"❌ {error_msg}")
            self.initialization_error = error_msg
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """サービス状態を取得"""
        return {
            "initialized": self.initialized,
            "initialization_error": self.initialization_error,
            "active_sessions": len(self.sessions),
            "service_uptime": time.time() if self.initialized else None
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """データベース統計情報を取得"""
        if not self.initialized or not self.rag_bot:
            return {"error": "RAGボットが初期化されていません"}
        
        try:
            # データベース統計情報を取得
            if hasattr(self.rag_bot, 'metadatas') and self.rag_bot.metadatas:
                total_docs = len(self.rag_bot.metadatas)
                
                文献名_set = set()
                樹種_set = set()
                章_set = set()
                
                for metadata in self.rag_bot.metadatas:
                    if metadata.get('文献名'):
                        文献名_set.add(metadata['文献名'])
                    if metadata.get('樹種') and metadata['樹種'].strip():
                        樹種_set.add(metadata['樹種'])
                    if metadata.get('章') and metadata['章'].strip():
                        章_set.add(metadata['章'])
                
                return {
                    "total_documents": total_docs,
                    "unique_literature": len(文献名_set),
                    "unique_species": len(樹種_set),
                    "unique_chapters": len(章_set),
                    "literature_list": sorted(list(文献名_set))[:10],  # 最初の10件
                    "species_list": sorted(list(樹種_set)),
                    "active_sessions": len(self.sessions)
                }
            else:
                return {"error": "データベース情報が取得できません"}
                
        except Exception as e:
            return {"error": f"統計情報取得エラー: {str(e)}"}
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """新しいセッションを作成"""
        if session_id is None:
            session_id = f"session_{int(time.time() * 1000)}"
        
        self.sessions[session_id] = {
            "created_at": datetime.now(),
            "chat_history": [],
            "last_activity": datetime.now(),
            "request_count": 0
        }
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """セッション情報を取得"""
        return self.sessions.get(session_id)
    
    def update_session_activity(self, session_id: str):
        """セッションの最終活動時間を更新"""
        if session_id in self.sessions:
            self.sessions[session_id]["last_activity"] = datetime.now()
            self.sessions[session_id]["request_count"] += 1
    
    def reset_session(self, session_id: str) -> bool:
        """セッションの会話履歴をリセット"""
        if session_id in self.sessions:
            self.sessions[session_id]["chat_history"] = []
            self.sessions[session_id]["last_activity"] = datetime.now()
            return True
        return False
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """古いセッションをクリーンアップ"""
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, session_data in self.sessions.items():
            age = current_time - session_data["last_activity"]
            if age.total_seconds() > max_age_hours * 3600:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        return len(expired_sessions)
    
    def chat(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """チャット処理のメインメソッド"""
        if not self.initialized:
            return {
                "success": False,
                "error": {
                    "code": "NOT_INITIALIZED",
                    "message": self.initialization_error or "RAGボットが初期化されていません"
                }
            }
        
        try:
            # リクエストデータのバリデーション
            question = request_data.get("question", "").strip()
            if not question:
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_QUESTION",
                        "message": "質問が空です"
                    }
                }
            
            # セッション管理
            session_id = request_data.get("session_id")
            if session_id:
                if session_id not in self.sessions:
                    session_id = self.create_session(session_id)
                self.update_session_activity(session_id)
                chat_history = self.sessions[session_id]["chat_history"]
            else:
                chat_history = []
            
            # 将来の拡張項目（現在は使用しないが構造として準備）
            user_info = request_data.get("user_info", {})
            species_filter = request_data.get("species_filter")
            search_options = request_data.get("search_options", {})
            
            # RAGボットの会話履歴を設定
            self.rag_bot.chat_history = chat_history.copy()
            
            # RAG実行
            start_time = time.time()
            response, metadata_list, referenced_docs = self.rag_bot.run_chat(question)
            processing_time = time.time() - start_time
            
            # 会話履歴を更新
            chat_history.append({"role": "user", "content": question})
            chat_history.append({"role": "assistant", "content": response})
            
            # 履歴の長さ制限
            if len(chat_history) > 10:
                chat_history = chat_history[-10:]
            
            # セッションに履歴を保存
            if session_id:
                self.sessions[session_id]["chat_history"] = chat_history
            
            # 参照ドキュメント情報を整理
            references = self._format_references(metadata_list)
            
            # トークン使用量情報
            token_info = None
            if self.rag_bot.track_tokens and self.rag_bot.token_tracker:
                token_info = {
                    "session_summary": self.rag_bot.token_tracker.get_session_summary()
                }
            
            return {
                "success": True,
                "data": {
                    "response": response,
                    "references": references,
                    "session_id": session_id,
                    "processing_time": round(processing_time, 2),
                    "token_info": token_info,
                    "metadata": {
                        "question_length": len(question),
                        "response_length": len(response),
                        "reference_count": len(references)
                    }
                }
            }
            
        except Exception as e:
            error_msg = f"チャット処理エラー: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"スタックトレース: {traceback.format_exc()}")
            
            return {
                "success": False,
                "error": {
                    "code": "CHAT_ERROR",
                    "message": error_msg
                }
            }
    
    def _format_references(self, metadata_list: List[Dict]) -> List[Dict]:
        """参照ドキュメント情報をAPI用に整形"""
        references = []
        seen_refs = set()
        
        for metadata in metadata_list:
            # 重複除去のためのキー
            ref_key = f"{metadata.get('文献名', '')}_{metadata.get('ページ', '')}"
            
            if ref_key not in seen_refs:
                seen_refs.add(ref_key)
                references.append({
                    "literature": metadata.get('文献名', ''),
                    "page": metadata.get('ページ', ''),
                    "chapter": metadata.get('章', ''),
                    "section": metadata.get('節', ''),
                    "category": metadata.get('区分', ''),
                    "species": metadata.get('樹種', ''),
                    "row_number": metadata.get('row_number', '')
                })
        
        return references


# グローバルサービスインスタンス
_rag_service = None

def get_rag_service() -> RAGApiService:
    """RAGサービスのシングルトンインスタンスを取得"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGApiService()
        # アプリ起動時の初期化は遅延実行
        # （アプリの起動速度を向上させるため）
    return _rag_service
