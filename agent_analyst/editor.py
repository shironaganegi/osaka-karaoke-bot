import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def refine_article(draft_text):
    """
    Acts as a sharp tech editor to refine and humanize the AI-generated draft.
    """
    if not api_key:
        print("WARNING: GEMINI_API_KEY is missing. Editor bypass.")
        return draft_text

    model = genai.GenerativeModel('gemini-1.5-pro')
    
    system_prompt = """
あなたは伝説のテックメディア「白ネギ・テック」の辛口編集長です。
提出されたAI下書きを、読者の魂を揺さぶるような、エモーショナルで拡散されやすい文章にリライトしてください。

【編集方針】
1. 「である調」と「ですます調」を効果的に使い分け、リズムを作る。
2. 専門用語は、初心者でもイメージが湧く比喩に変換する。
3. AI特有の「〜です。〜ます。」の繰り返しなど、単調な文章構造を徹底的に排除する。
4. 読者に直接問いかけたり、驚きを共有したりする「会話感」を出す。
5. 冒頭で「なぜ今、この記事を読む必要があるのか」を猛烈にアピールする。

【絶対遵守事項】
- 記事内に含まれる `{{RECOMMENDED_PRODUCTS}}` という文字列は、後に商品リンクが挿入される重要な場所です。**絶対に削除・移動・変更しないでください。**
- `<div class="recommend-box">...</div>` などのHTMLタグが含まれている場合、それはアフィリエイトリンクです。**一文字も変えず、そのまま保持してください。**
- Markdownの構造（# や ##）は維持してください。
"""

    prompt = f"{system_prompt}\n\n以下が編集対象の原稿です：\n\n{draft_text}"

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Editor refinement failed: {e}")
        return draft_text # Fallback to original
