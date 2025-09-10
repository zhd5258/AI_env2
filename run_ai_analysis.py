
import json
import os
import time
from modules.pdf_processor import PDFProcessor
from modules.local_ai_analyzer import LocalAIAnalyzer

def extract_bid_text(pdf_path, temp_text_path):
    """Extracts text from the bid PDF and saves it to a temporary file."""
    print(f"--- Step 1: Extracting text from Bid Document: '{pdf_path}' ---")
    if not os.path.exists(pdf_path):
        print(f"Error: Bid PDF file not found at '{pdf_path}'")
        return False
        
    processor = PDFProcessor(pdf_path)
    pages = processor.extract_text_per_page()
    
    if not pages:
        print("Error: Could not extract any text from the bid PDF.")
        return False
        
    full_text = "\n".join(pages)
    
    with open(temp_text_path, 'w', encoding='utf-8') as f:
        f.write(full_text)
        
    print(f"Successfully extracted bid text to '{temp_text_path}'.")
    return True

def create_analysis_prompt(rule, bid_document_text):
    """Creates a specific prompt for a single scoring rule."""
    
    # Special handling for the price score
    if "价格" in rule['item']:
        return f'''
        你是一个专业的评标专家。你的任务是分析以下投标文件内容，并仅从中提取出总投标报价。

        评分规则项: "{rule['item']}"
        规则描述: "{rule['description']}"

        请仔细阅读下面的投标文件全文，找到并提取出总投标报价的明确金额。

        输出一个JSON对象，必须包含以下键：
        - "item": "{rule['item']}"
        - "score": 0
        - "reasoning": "价格分需要与其他投标人比较后计算。此处仅提取报价金额。"
        - "extracted_price": "此处填入你找到的总报价金额"

        投标文件全文如下：
        ---
        {bid_document_text}
        ---
        '''

    # Standard prompt for all other rules
    return f'''
    你是一个严格的、只关注指令的AI评标助手。
    你的唯一任务是根据一项具体的评分规则，对一份投标文件进行评估，并严格按照JSON格式输出结果。

    **绝对指令:**
    1.  **不要**进行任何思考、总结或提供建议。
    2.  **不要**输出任何JSON格式之外的文本、注释或标记。
    3.  你的输出必须是一个可以直接通过JSON解析器解析的、格式正确的JSON对象。

    **评估任务:**
    1.  **评分规则项:** "{rule['item']}"
    2.  **最高分:** {rule['max_score']}
    3.  **评分标准:** "{rule['description']}"
    4.  **评估对象:** 下文提供的投标文件全文。

    **执行步骤:**
    1.  在投标文件中寻找与“评分规则项”相关的内容。
    2.  根据找到的证据和“评分标准”，给出一个具体的分数（0 到 {rule['max_score']} 之间）。
    3.  撰写评分理由，理由必须明确、客观，并引用投标文件中的关键信息作为依据。

    **输出格式（必须严格遵守）:**
    ```json
    {{
      "item": "{rule['item']}",
      "score": <你给出的分数 (数字)>,
      "reasoning": "<你的详细评分理由>"
    }}
    ```

    **投标文件全文如下:**
    ---
    {bid_document_text}
    ---
    '''

def main():
    bid_pdf_path = r'D:\user\PythonProject\AI_env2\uploads\1_bid_武汉新国铁集装箱涂装线大修投标文件.pdf'
    rules_json_path = 'scoring_rules.json'
    temp_text_path = 'bid_text.tmp'
    output_analysis_path = 'analysis_result.json'

    # --- Step 1: Extract text from bid PDF ---
    if not extract_bid_text(bid_pdf_path, temp_text_path):
        return

    # --- Step 2: Load rules and bid text ---
    print(f"\n--- Step 2: Loading rules and bid text ---")
    try:
        with open(rules_json_path, 'r', encoding='utf-8') as f:
            scoring_rules = json.load(f)
        with open(temp_text_path, 'r', encoding='utf-8') as f:
            bid_text = f.read()
        print("Successfully loaded scoring rules and bid text.")
    except FileNotFoundError as e:
        print(f"Error: Could not find a necessary file. Details: {e}")
        return
    
    # --- Step 3: Iterate and analyze each rule ---
    print(f"\n--- Step 3: Starting AI analysis for {len(scoring_rules)} rules ---")
    final_analysis_results = []
    analyzer = LocalAIAnalyzer()

    for i, rule in enumerate(scoring_rules):
        print(f"\nAnalyzing rule {i+1}/{len(scoring_rules)}: '{rule['item']}'...")
        
        prompt = create_analysis_prompt(rule, bid_text)
        
        ai_response = analyzer.analyze_text(prompt)
        
        clean_response = ai_response.strip().replace('```json', '').replace('```', '').strip()
        
        try:
            result = json.loads(clean_response)
            final_analysis_results.append(result)
            print(f"Successfully analyzed. Score: {result.get('score')}")
        except json.JSONDecodeError:
            print("Error: AI response for this rule was not valid JSON.")
            print("--- Raw AI Response ---")
            print(ai_response)
            # Add a placeholder for the failed item
            final_analysis_results.append({
                "item": rule['item'],
                "score": 0,
                "reasoning": "Failed to parse AI response. See logs for details."
            })
        
        time.sleep(1) # Add a small delay to avoid overwhelming the AI server

    # --- Step 4: Save and print final results ---
    print(f"\n--- Step 4: AI Analysis Complete ---")
    with open(output_analysis_path, 'w', encoding='utf-8') as f:
        json.dump(final_analysis_results, f, ensure_ascii=False, indent=2)
    
    print(f"Full analysis saved to '{output_analysis_path}'.")
    print("\n--- Final Analysis Result ---")
    print(json.dumps(final_analysis_results, ensure_ascii=False, indent=2))

    # --- Step 5: Cleanup ---
    if os.path.exists(temp_text_path):
        os.remove(temp_text_path)
        print(f"\n--- Step 5: Cleaned up temporary file: {temp_text_path} ---")

if __name__ == '__main__':
    main()
