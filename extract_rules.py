
import json
import os
from modules.local_ai_analyzer import LocalAIAnalyzer

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
        print(f"Error: Could not find a necessary file. Make sure '{tender_text_path}' and '{prompt_template_path}' exist. Details: {e}")
        return

    # --- 2. Construct the full prompt ---
    prompt = prompt_template.replace('{TENDER_TEXT_PLACEHOLDER}', tender_text)

    # --- 3. Call the AI analyzer ---
    print("Connecting to AI model to extract scoring rules...")
    analyzer = LocalAIAnalyzer()
    ai_response = analyzer.analyze_text(prompt)

    if "Error: Could not connect" in ai_response:
        print(ai_response)
        return

    # --- 4. Clean the AI response ---
    print("AI response received. Cleaning and validating JSON...")
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
        print(f"Scoring rules successfully saved to {output_json_path}.")
        
        # --- 6. Pretty-print the result ---
        print("\n--- Extracted Scoring Rules ---")
        print(json.dumps(parsed_json, ensure_ascii=False, indent=2))

    except json.JSONDecodeError:
        print("Error: AI response was not valid JSON after cleaning.")
        print("--- Raw AI Response ---")
        print(ai_response)

if __name__ == '__main__':
    main()
