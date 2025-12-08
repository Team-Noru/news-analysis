from keybert import KeyBERT

with open("news2.txt", "r", encoding="utf-8") as file:
    doc = file.read()

kw_model = KeyBERT()
keywords = kw_model.extract_keywords(doc)

print(keywords)