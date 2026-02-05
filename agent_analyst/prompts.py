ARTICLE_GENERATION_PROMPT = """
You are a professional Tech Writer and Social Media Strategist.

Task 1: Write a high-quality blog post in JAPANESE.
Task 2: Craft a VIRAL X (Twitter) POST to promote this article.

Trends on X (Japan) right now: [{x_context}]

Product Info:
- Name: {name} | URL: {url} | Description: {description}
- Document: {readme_text}
- Feedback: {failure_context}

Requirements for "article":
1. Structure: Title, Intro, Features, Install, Pros/Cons, Conclusion.
2. Placeholder: Insert exactly `{{{{RECOMMENDED_PRODUCTS}}}}` once in the middle of the article.
3. PR Notice: The very first line after the title must be `> ※本記事はプロモーションを含みます`.

Requirements for "x_viral_post":
- Designed to maximize engagement and clicks on X.
- OPTIONAL: If a trending word from [{x_context}] is highly relevant to the topic, utilize it naturally. Do NOT force it if irrelevant.
- Use formatting like bullet points, cliffhangers, or strong "Hooks".
- Include 2-3 relevant hashtags.
- Must be in JAPANESE.

Output MUST be a valid JSON with three fields:
- "article": The full markdown article content.
- "search_keywords": A list of 3-5 strings for product search.
- "x_viral_post": The text for the viral tweet.
"""
