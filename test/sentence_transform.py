# 安装必要的库
# pip install sentence-transformers torch
 
from sentence_transformers import SentenceTransformer
 
# 加载一个预训练模型，例如 all-MiniLM-L6-v2，它平衡了速度与效果，维度为384
model = SentenceTransformer('all-MiniLM-L6-v2')
 
# 准备文本
sentences = [
    "Elasticsearch是一个基于Lucene的搜索和分析引擎。",
    "向量搜索通过语义相似度来匹配文档。",
    "BERT模型能够生成高质量的文本嵌入向量。"
]
 
# 生成向量
embeddings = model.encode(sentences)
 
print(f"生成的向量维度: {embeddings.shape}") # 例如 (3, 384)
print(f"第一条文本的向量样例: {embeddings[0][:5]}...") # 打印前5个值