import json
from modules.local_ai_analyzer import LocalAIAnalyzer
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """
    Main function to extract scoring rules from a tender document using an AI model.
    """
    tender_text_path = 'tender_text.tmp'
    prompt_template_path = 'prompt.txt'
    output_json_path = 'scoring_rules.json'

    # --- 1. Read necessary files ---
    try:
        with open(tender_text_path, 'r', encoding='utf-8') as f:
            tender_text = f.read()
        with open(prompt_template_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError as e:
        logger.error(
            f"Error: Could not find a necessary file. Make sure '{tender_text_path}' and '{prompt_template_path}' exist. Details: {e}"
        )
        return

    # --- 2. Construct the full prompt ---
    prompt = prompt_template.replace('{TENDER_TEXT_PLACEHOLDER}', tender_text)

    # --- 3. Call the AI analyzer ---
    logger.info('Connecting to AI model to extract scoring rules...')
    analyzer = LocalAIAnalyzer()
    ai_response = analyzer.analyze_text(prompt)

    if 'Error: Could not connect' in ai_response:
        logger.error(ai_response)
        return

    # --- 4. Clean the AI response ---
    logger.info('AI response received. Cleaning and validating JSON...')
    clean_response = ai_response.strip()
    if clean_response.startswith('```json'):
        clean_response = clean_response[7:]
    if clean_response.endswith('```'):
        clean_response = clean_response[:-3]
    clean_response = clean_response.strip()

    # --- 5. Validate and save the JSON ---
    try:
        parsed_json = json.loads(clean_response)
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, ensure_ascii=False, indent=2)
        logger.info(f'Scoring rules successfully saved to {output_json_path}.')

        # --- 6. Pretty-print the result ---
        logger.info('\n--- Extracted Scoring Rules ---')
        logger.info(json.dumps(parsed_json, ensure_ascii=False, indent=2))

    except json.JSONDecodeError:
        logger.error('Error: AI response was not valid JSON after cleaning.')
        logger.error('--- Raw AI Response ---')
        logger.error(ai_response)


if __name__ == '__main__':
    main()
