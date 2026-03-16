# !pip install pinecone-client==3.2.2
from langchain_community.vectorstores import Pinecone
from langchain_openai import OpenAIEmbeddings
# from pinecone import Pinecone
from dotenv import load_dotenv
import os


load_dotenv()


""""
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
index = pc.Index(os.environ.get("PINECONE_INDEX"))
for ids in index.list():
    index.delete(ids=[ids])
"""
embeddings = OpenAIEmbeddings()
vectorstore = Pinecone.from_existing_index(os.environ["PINECONE_INDEX"], embeddings)
vectorstore.delete(delete_all=True)
