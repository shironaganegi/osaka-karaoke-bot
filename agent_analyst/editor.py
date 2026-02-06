import os
# import google.generativeai as genai # REMOVED
from agent_analyst.llm_client import get_gemini_response
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini - API Key check is done inside llm_client
api_key = os.getenv("GEMINI_API_KEY")

def refine_article(draft_text):
    """
    Acts as a sharp tech editor to refine and humanize the AI-generated draft.
    """
    if not api_key:
        print("WARNING: GEMINI_API_KEY is missing. Editor bypass.")
        return draft_text

    try:
        system_prompt = """
あなたはテック系メディア「白ネギ・テック」の敏腕編集長です。
提出されたAI下書きを、読者の知的好奇心を刺激する、エモーショナルで読み応えのある記事にリライトしてください。

【編集方針】
1. リズム感: 「である調」と「ですます調」を適切に使い分け、読み手を飽きさせないリズムを作る。
2. 比喩表現: 専門用語は噛み砕き、直感的に伝わる比喩に変換する。
3. 脱AI感: 「〜です。〜ます。」の機械的な繰り返しを排除し、人間味のある語り口にする。
4. 共感と問いかけ: 読者の課題に寄り添い、「そう、それが欲しかったんだ！」と思わせる共感を呼ぶ。
5. 導入のフック: 冒頭で「この記事を読むメリット」を明確に示し、読者を惹きつける。

【トーン＆マナー】
- 過度に攻撃的な言葉遣い（「お前」「ブチ壊す」など）は避け、"辛口だが愛がある" 知的な批評スタイルを保つこと。
- 読者を煽るのではなく、鼓舞するような熱量を持つこと。

【絶対遵守事項】
- **出力には「前置き」や「挨拶」を一切含めないこと。** リライト後の記事本文のみを出力してください。
- 記事内に含まれるHTMLタグ（`<div class="recommend-box">...</div>` や `<iframe>...</iframe>` など）は、アフィリエイトリンクや埋め込みコンテンツです。
- **これらは一文字たりとも変更・削除・移動せず、元の位置にそのまま維持してください。** AIが勝手に解釈して要約したり、Markdownに変換したりすることは厳禁です。
- Markdownの構造（# や ## などの見出し）は維持してください。
"""
        prompt = f"{system_prompt}\n\n以下が編集対象の原稿です（出力は記事本文のみ）：\n\n{draft_text}"

        candidate_models = [
            'gemini-2.0-flash-lite-001',
            'gemini-flash-latest',
            'gemini-2.0-flash',
            'gemini-pro-latest'
        ]

        response_data = None
        for model_name in candidate_models:
            print(f"Editor optimizing using: {model_name}...")
            # No JSON constraint, we want raw text (markdown)
            response_data = get_gemini_response(prompt, model_name)
            if response_data:
                break
                
        if not response_data:
            print("All editor models failed.")
            return draft_text

        # Extract text from REST response
        try:
            return response_data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
             print(f"Editor response parsing failed: {response_data}")
             return draft_text

    except Exception as e:
        print(f"Editor refinement failed: {e}")
        return draft_text # Fallback to original
