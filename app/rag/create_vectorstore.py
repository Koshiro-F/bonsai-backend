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

load_dotenv(dotenv_path=".env.local")

FOLDER_PATH = "/root/workspaces/rag-streamlit-orion/data/input/"
PROCESSED_FILES_TXT = "/root/workspaces/rag-streamlit-orion/data/processed_files.txt"
VECTORSTORE_PATH = "/root/workspaces/rag-streamlit-orion/data/vectorstore"


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
        # Get Elements
        raw_pdf_elements = partition_pdf(
            filename=FOLDER_PATH + file,
            languages=["jpn", "eng"],
            strategy="hi_res",
            extract_images_in_pdf=True,
            extract_image_block_types=["Image", "Table"],
            extract_image_block_to_payload=True,
            infer_table_structure=True,
        )

        images = []
        texts = []

        el_dict_list = [el.to_dict() for el in raw_pdf_elements]

        for i, el in enumerate(el_dict_list):
            not_table_title = True
            if i < len(el_dict_list) - 1:
                if el["type"] == "Title" and el_dict_list[i + 1]["type"] == "Table":
                    el_dict_list[i + 1]["text"] = (
                        el["text"] + "\n" + el_dict_list[i + 1]["text"]
                    )
                    not_table_title = False
            if el["type"] in ["Image", "Table"]:
                images.append(el)
            elif not_table_title:
                texts.append(el)

        images = self.del_small_images(images)

        texts = self.merge_texts(texts, FOLDER_PATH, file)

        return images, texts

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
                            "type": chunk["type"],
                            "file_directory": chunk["metadata"]["file_directory"],
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
                            "type": "Image",
                            "file_directory": image["metadata"]["file_directory"],
                            "filename": image["metadata"]["filename"],
                            "page_number": image["metadata"]["page_number"],
                            "image_base64": image["metadata"]["image_base64"],
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
