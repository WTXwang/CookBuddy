from recipes.extractor import llm_extract_recipe
text = '# 番茄炒蛋的做法\n## 必备原料和工具\n- 番茄 2个\n- 鸡蛋 3个\n- 食用油 适量\n- 盐 适量\n## 操作\n1. 鸡蛋打散，番茄切块\n2. 炒鸡蛋盛出\n3. 炒软番茄，倒回鸡蛋翻匀'
r = llm_extract_recipe(text)
print(r)
print(f'标题={r["title"]}')
print(f'核心={r["core_ingredients"]}')
print(f'调料={r["seasonings"]}')
print(f'厨具={r["equipment"]}')