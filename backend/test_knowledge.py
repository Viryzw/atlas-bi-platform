from knowledge_base import retrieve_knowledge

results = retrieve_knowledge("我想看销售额趋势")
for doc in results:
    print(doc.page_content)
    print("---")