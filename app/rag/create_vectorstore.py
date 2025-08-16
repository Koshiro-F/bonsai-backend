import os
import time
import warnings

from dotenv import load_dotenv
from langchain.schema.document import Document
from langchain.schema.messages import HumanMessage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from unstructured.partition.pdf import partition_pdf
from google.cloud import documentai
import pdf_chunking

# スクリプトファイルの位置を基準にパスを計算（カレントディレクトリに依存しない）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.join(SCRIPT_DIR, "..", "..")
ENV_PATH = os.path.join(BACKEND_ROOT, ".env.local")

load_dotenv(dotenv_path=ENV_PATH)

# Google Cloud認証情報の設定（環境変数が設定されていない場合のデフォルト）
if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    # デフォルトの認証情報パス（ユーザーのホームディレクトリ相対）
    default_creds_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    if os.path.exists(default_creds_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = default_creds_path
    else:
        print("警告: Google Cloud認証情報が見つかりません。GOOGLE_APPLICATION_CREDENTIALS環境変数を設定してください。")

FOLDER_PATH = os.path.join(BACKEND_ROOT, "data", "input")
PROCESSED_FILES_TXT = os.path.join(BACKEND_ROOT, "data", "processed_files.txt")
VECTORSTORE_PATH = os.path.join(BACKEND_ROOT, "data", "vectorstore")


class CreateVectorstore:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
        )
        if os.path.exists(VECTORSTORE_PATH):
            print("--------------------------------")
            warnings.warn("vectorstore already exists, you may want to delete it")
            print("vectorstore will not be overwritten, adding new documents")
            print("--------------------------------")
        self.vectorstore = Chroma(
            embedding_function=self.embeddings, persist_directory=VECTORSTORE_PATH
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512, chunk_overlap=128
        )

        self.chat_image_summarizer = ChatOpenAI(model="gpt-4.1-mini")

    def main(self):
        if os.path.exists(PROCESSED_FILES_TXT):
            with open(PROCESSED_FILES_TXT, "r") as f:
                processed_files = set(f.read().splitlines())
        else:
            processed_files = set()

        for file in os.listdir(FOLDER_PATH):
            if file.split(".")[-1] == "pdf":
                if file not in processed_files:
                    print(file)
                    images, texts = self.process_pdf(file)
                    print("partation, done!")
                    images = self.add_summary(images)
                    print("summarize, done!")
                    self.add_vectorstore(
                        self.vectorstore, texts, images, self.text_splitter
                    )
                    processed_files.add(file)

            with open(PROCESSED_FILES_TXT, "w") as f:
                f.write("\n".join(processed_files))
            self.vectorstore.persist()

    def process_pdf(self, file):
        # DocumentAI documentを取得
        document = self.get_documentai_document(file)
        base_metadata = {
            "source_file": os.path.join(FOLDER_PATH, file),
            "filename": file,
        }
        # チャンク抽出・結合
        chunks = pdf_chunking.extract_document_chunks(document, base_metadata)
        # 距離閾値を30pxに拡大
        chunks = pdf_chunking.merge_paragraph_chunks(chunks, max_distance=30, max_chars_per_chunk=1500)
        # 3文字以下の短いチャンクを除去
        chunks = [c for c in chunks if len(c["text"].strip()) > 3]
        # 画像・表要素は従来通り抽出
        images = [c for c in chunks if c["metadata"]["chunk_type"] in ["Image", "Table"]]
        texts = [c for c in chunks if c["metadata"]["chunk_type"] == "paragraph" or c["metadata"]["chunk_type"] == "merged_paragraph"]
        return images, texts

    def get_documentai_document(self, file):
        # test.pyのprocess_documentを参考にDocumentAI documentを取得
        project_id = "utopian-saga-466802-m5"
        location = "us"
        processor_id = "e794632016082b0"
        processor_version = "pretrained-ocr-v2.0-2023-06-02"
        mime_type = "application/pdf"
        client = documentai.DocumentProcessorServiceClient()
        name = client.processor_version_path(project_id, location, processor_id, processor_version)
        with open(os.path.join(FOLDER_PATH, file), "rb") as image:
            image_content = image.read()
        request = documentai.ProcessRequest(
            name=name,
            raw_document=documentai.RawDocument(content=image_content, mime_type=mime_type),
        )
        result = client.process_document(request=request)
        return result.document

    def del_small_images(self, images, max_kb=30):
        over_max_kb_image_list = []
        for image in images:
            if image["type"] == "Image":
                base64_data = image["metadata"]["image_base64"]
                # パディング文字を除去
                padding_characters = base64_data.count("=")
                base64_length = len(base64_data) - padding_characters
                # 元のデータサイズを計算
                original_size = (base64_length * 3) // 4
                if original_size > max_kb * 1024:
                    over_max_kb_image_list.append(image)
            else:
                over_max_kb_image_list.append(image)
        return over_max_kb_image_list

    def merge_texts(self, texts, file_directory, filename):
        combined_texts = {}

        for text in texts:
            page = text["metadata"]["page_number"]
            words = text["text"]

            if page in combined_texts:
                combined_texts[page] += "\n" + words
            else:
                combined_texts[page] = words

        result = [
            {
                "type": "Text",
                "text": all_words,
                "metadata": {
                    "page_number": page,
                    "file_directory": file_directory,
                    "filename": filename,
                },
            }
            for page, all_words in combined_texts.items()
        ]

        return result

    def add_summary(self, images):
        for image in images:
            image["summary"] = self.image_summarize(image)
        return images

    def image_summarize(self, image):
        if image["type"] == "Table":
            prompt = (
                "表が画像データとして提供されています。"
                "画像データをもとに、この表に含まれる情報をもれなく正確に、日本語の文章で説明してください。"
                "ただし与えられた表の画像が読み取りにくい場合には、次に提供するHTML形式の表を使用して情報をもれなく正確に日本語で説明してください。"
                "表のHTML形式: {html}"
                "また、HTML形式には誤字が含まれている可能性がありますので、以下のテキスト情報を参考にしてください。"
                "テキスト情報: {text}"
            ).format(html=image["metadata"]["text_as_html"], text=image["text"])
        else:
            prompt = "この画像に含まれる情報をもれなく正確に日本語で説明してください。"

        img_base64 = image["metadata"]["image_base64"]

        msg = self.chat_image_summarizer.invoke(
            [
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            },
                        },
                    ]
                )
            ]
        )

        return msg.content

    def add_vectorstore(self, vectorstore, texts, images, text_splitter):
        chunks = []
        for text in texts:
            chunk_list = text_splitter.split_text(text["text"])
            for chunk in chunk_list:
                chunk_dict = text.copy()
                chunk_dict["text"] = chunk
                chunks.append(chunk_dict)

        for i, chunk in enumerate(chunks):
            vectorstore.add_documents(
                [
                    Document(
                        page_content=chunk["text"],
                        metadata={
                            "type": chunk["metadata"]["chunk_type"],
                            "filename": chunk["metadata"]["filename"],
                            "page_number": chunk["metadata"]["page_number"],
                            "image_base64": "",
                        },
                    )
                ]
            )

        img_chunks = []
        for image in images:
            img_chunk_list = text_splitter.split_text(image["summary"])
            for img_chunk in img_chunk_list:
                img_chunk_dict = image.copy()
                img_chunk_dict["summary"] = img_chunk
                img_chunks.append(img_chunk_dict)

        for i, image in enumerate(img_chunks):
            vectorstore.add_documents(
                [
                    Document(
                        page_content=image["summary"],
                        metadata={
                            "type": image["metadata"]["chunk_type"] if "chunk_type" in image["metadata"] else "Image",
                            "file_directory": image["metadata"]["file_directory"],
                            "filename": image["metadata"]["filename"],
                            "page_number": image["metadata"]["page_number"],
                            "image_base64": image["metadata"].get("image_base64", ""),
                        },
                    )
                ]
            )


if __name__ == "__main__":
    start_time = time.time()
    cv = CreateVectorstore()
    cv.main()
    end_time = time.time()
    print(f"Time taken: {(end_time - start_time) / 60} minutes")
