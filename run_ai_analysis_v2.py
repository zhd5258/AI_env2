import json
import os
import time
from modules.pdf_processor import PDFProcessor
from modules.local_ai_analyzer import LocalAIAnalyzer

LOG_FILE = 'ai_responses.log'


def log_message(message):
    """Appends a message to the log file."""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} - {message}\n')


def extract_bid_text(pdf_path, temp_text_path):
    """Extracts text from the bid PDF and saves it to a temporary file."""
    log_message(f"Step 1: Extracting text from Bid Document: '{pdf_path}'")
    if not os.path.exists(pdf_path):
        log_message(f"Error: Bid PDF file not found at '{pdf_path}'")
        return False
    processor = PDFProcessor(pdf_path)
    pages = processor.extract_text_per_page()
    if not pages:
        log_message('Error: Could not extract any text from the bid PDF.')
        return False
    full_text = '\n'.join(pages)
    with open(temp_text_path, 'w', encoding='utf-8') as f:
        f.write(full_text)
    log_message(f"Successfully extracted bid text to '{temp_text_path}'.")
    return True


def create_analysis_prompt(rule, bid_document_text):
    """Creates a specific, strict prompt for a single scoring rule."""
    item_json = json.dumps(rule['item'], ensure_ascii=False)
    description_json = json.dumps(rule['description'], ensure_ascii=False)

    if '价格' in rule['item']:
        return f"""
        **AI Assistant Instructions:**
        - Your task is to find the total bid price in the provided text.
        - You MUST ONLY output a JSON object.
        - Do NOT include any other text, explanations, or markdown.
        - The JSON object must have the keys "item", "score", "reasoning", and "extracted_price".

        **Rule Item:** {item_json}
        **Rule Description:** {description_json}
        **Document to Analyze:** Provided below.

        **Required JSON Output Format:**
        ```json
        {{
          "item": {item_json},
          "score": 0,
          "reasoning": "价格分需要与其他投标人比较后计算。此处仅提取报价金额。",
          "extracted_price": "YOUR_EXTRACTED_PRICE_HERE"
        }}
        ```
        ---
        **Document Text:**
        {bid_document_text}
        ---
        """
    else:
        return f"""
        **AI Assistant Instructions:**
        - Your only task is to evaluate a bid document based on a specific rule and output a JSON object.
        - You MUST ONLY output a JSON object.
        - Do NOT output any text, explanations, apologies, or markdown before or after the JSON object.
        - Your entire response must be a single, valid JSON object.

        **Evaluation Task:**
        1.  **Rule Item:** {item_json}
        2.  **Max Score:** {rule['max_score']}
        3.  **Scoring Standard:** {description_json}
        4.  **Document to Analyze:** Provided below.

        **Execution Steps:**
        1.  Find evidence in the document related to the "Rule Item".
        2.  Based on the "Scoring Standard", assign a numeric score between 0 and {rule['max_score']}.
        3.  Write a justification for your score, citing evidence from the document.

        **Required JSON Output Format:**
        ```json
        {{
          "item": {item_json},
          "score": <your_assigned_score_as_a_number>,
          "reasoning": "<your_detailed_justification_here>"
        }}
        ```
        ---
        **Document Text:**
        {bid_document_text}
        ---
        """


def main():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    bid_pdf_path = r'D:\user\PythonProject\AI_env2\uploads\1_bid_武汉新国铁集装箱涂装线大修投标文件.pdf'
    rules_json_path = 'scoring_rules.json'
    temp_text_path = 'bid_text.tmp'
    output_analysis_path = 'analysis_result.json'

    print('-- AI Bid Analysis v3 --')
    print(f'Detailed logs will be written to: {LOG_FILE}')

    if not extract_bid_text(bid_pdf_path, temp_text_path):
        return

    log_message('Step 2: Loading rules and bid text.')
    try:
        with open(rules_json_path, 'r', encoding='utf-8') as f:
            scoring_rules = json.load(f)
        with open(temp_text_path, 'r', encoding='utf-8') as f:
            bid_text = f.read()
        log_message('Successfully loaded scoring rules and bid text.')
    except FileNotFoundError as e:
        log_message(f'Error: Could not find a necessary file. Details: {e}')
        print(f'Error: Could not find a necessary file. Check {LOG_FILE} for details.')
        return

    print(
        f'\nStarting AI analysis for {len(scoring_rules)} rules. This may take several minutes.'
    )
    final_analysis_results = []
    analyzer = LocalAIAnalyzer()

    for i, rule in enumerate(scoring_rules):
        progress_prefix = f'({i + 1}/{len(scoring_rules)})'
        print(f"{progress_prefix} Analyzing '{rule['item']}'...", end='', flush=True)

        prompt = create_analysis_prompt(rule, bid_text)
        log_message(f'Analyzing rule: {rule["item"]}')

        ai_response = analyzer.analyze_text(prompt)

        clean_response = (
            ai_response.strip().replace('```json', '').replace('```', '').strip()
        )

        try:
            result = json.loads(clean_response)
            final_analysis_results.append(result)
            print(f' Done. [Score: {result.get("score", "N/A")}]')
        except json.JSONDecodeError:
            print(' Failed. (Invalid JSON response from AI)')
            log_message(f'Error parsing JSON for rule: {rule["item"]}')
            log_message('---' + ' Raw AI Response ---')
            log_message(ai_response)
            final_analysis_results.append(
                {
                    'item': rule['item'],
                    'score': 0,
                    'reasoning': 'Failed to parse AI response. See ai_responses.log for details.',
                }
            )

        time.sleep(1)

    print('\n--- AI Analysis Complete ---')
    with open(output_analysis_path, 'w', encoding='utf-8') as f:
        json.dump(final_analysis_results, f, ensure_ascii=False, indent=2)

    print(f"Full analysis saved to '{output_analysis_path}'.")
    print('\n--- Final Analysis Result ---')
    # Use a robust way to print the final result to avoid encoding errors
    try:
        with open(output_analysis_path, 'r', encoding='utf-8') as f:
            print(f.read())
    except Exception as e:
        print(
            f"Could not print final result. Please check the file '{output_analysis_path}'. Error: {e}"
        )

    if os.path.exists(temp_text_path):
        os.remove(temp_text_path)
        log_message(f'Cleaned up temporary file: {temp_text_path}')


if __name__ == '__main__':
    main()
