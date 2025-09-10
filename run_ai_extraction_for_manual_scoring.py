
import json
import os
import time
from modules.pdf_processor import PDFProcessor
from modules.local_ai_analyzer import LocalAIAnalyzer

LOG_FILE = 'ai_extraction.log'

def log_message(message):
    """Appends a message to the log file."""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def extract_bid_text(pdf_path):
    """Extracts full text from the bid PDF."""
    log_message(f"Extracting text from Bid Document: '{pdf_path}'")
    if not os.path.exists(pdf_path):
        log_message(f"Error: Bid PDF file not found at '{pdf_path}'")
        return None
    processor = PDFProcessor(pdf_path)
    pages = processor.extract_text_per_page()
    if not pages:
        log_message("Error: Could not extract any text from the bid PDF.")
        return None
    log_message("Successfully extracted bid text.")
    return "\n".join(pages)

def create_extraction_prompt(rule, bid_document_text):
    """Creates a simple prompt to extract evidence for a rule."""
    # Special prompt for the price rule
    if "价格" in rule['item']:
        return f'''
        **任务:** 从下面的投标文件中，找到并提取出“总投标报价”或类似的最终报价金额。

        **评分项:** "{rule['item']}"

        **要求:**
        - 直接返回你找到的包含报价金额的句子或段落。
        - 如果找不到明确的总报价，请回答“在文件中未找到明确的总投标报价”。
        - 不要添加任何额外的分析、评论或解释。

        **投标文件全文:**
        ---
        {bid_document_text}
        ---
        '''
    
    # Standard prompt for all other rules
    return f'''
    **任务:** 你是一个信息提取助手。请从下面的投标文件中，找到并提取出与给定的“评分项”最相关的原文段落或句子。

    **评分项:** "{rule['item']}"
    **评分标准:** "{rule['description']}"

    **要求:**
    - 你的回答必须只包含从投标文件中直接摘抄的原文内容。
    - 如果在文件中找不到任何相关内容，请只回答“在文件中未找到相关内容”。
    - 不要进行任何分析、打分、总结或添加任何额外的解释。

    **投标文件全文:**
    ---
    {bid_document_text}
    ---
    '''

def main():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    bid_pdf_path = r'D:\user\PythonProject\AI_env2\uploads\1_bid_武汉新国铁集装箱涂装线大修投标文件.pdf'
    rules_json_path = 'scoring_rules.json'
    output_markdown_path = 'manual_scoring_sheet.md'

    print("--- AI-Assisted Manual Scoring Sheet Generator ---")
    print(f"Logs will be written to: {LOG_FILE}")

    bid_text = extract_bid_text(bid_pdf_path)
    if not bid_text:
        print("Failed to extract text from bid document. Check logs for details.")
        return

    log_message("Loading scoring rules.")
    try:
        with open(rules_json_path, 'r', encoding='utf-8') as f:
            scoring_rules = json.load(f)
        log_message("Successfully loaded scoring rules.")
    except FileNotFoundError:
        log_message(f"Error: scoring_rules.json not found.")
        print("Error: scoring_rules.json not found. Please ensure the file exists.")
        return
    
    print(f"\nStarting AI evidence extraction for {len(scoring_rules)} rules. This may take a few minutes.")
    analyzer = LocalAIAnalyzer()
    markdown_content = "# 投标文件评估计分表\n\n"
    total_max_score = 0

    for i, rule in enumerate(scoring_rules):
        progress_prefix = f"({i+1}/{len(scoring_rules)})"
        print(f"{progress_prefix} Extracting evidence for '{rule['item']}'...", end='', flush=True)
        
        prompt = create_extraction_prompt(rule, bid_text)
        log_message(f"Extracting for rule: {rule['item']}")
        
        ai_response = analyzer.analyze_text(prompt).strip()
        log_message(f"AI Response: {ai_response}")
        
        markdown_content += f"## {i+1}. {rule['item']}\n\n"
        markdown_content += f"**满分:** {rule['max_score']}分\n\n"
        markdown_content += f"**评分标准:** {rule['description']}\n\n"
        markdown_content += f"**AI提取的相关证据:**\n"
        markdown_content += f"```\n{ai_response}\n```\n\n"
        markdown_content += f"**专家评分:** ____________ 分\n\n"
        markdown_content += f"**评分理由:**\n\n\n"
        markdown_content += f"---\n\n"
        
        print(" Done.")
        total_max_score += rule['max_score']
        time.sleep(1)

    markdown_content += f"## 总分\n\n"
    markdown_content += f"**满分合计:** {total_max_score}分\n\n"
    markdown_content += f"**最终得分:** ____________ 分\n"

    print(f"\n--- Extraction Complete ---")
    with open(output_markdown_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"Manual scoring sheet has been successfully generated: '{output_markdown_path}'")
    print("\n--- Content of the Scoring Sheet ---")
    print(markdown_content)

if __name__ == '__main__':
    main()
