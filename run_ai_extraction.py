
import json
import os
from modules.pdf_processor import PDFProcessor
from modules.local_ai_analyzer import LocalAIAnalyzer

def extract_and_save_text(pdf_path, temp_text_path):
    """Extracts text from a PDF and saves it to a temporary file."""
    print(f"Step 1: Extracting text from '{pdf_path}'...")
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at '{pdf_path}'")
        return False
        
    processor = PDFProcessor(pdf_path)
    pages = processor.extract_text_per_page()
    
    if not pages:
        print("Error: Could not extract any text from the PDF.")
        return False
        
    full_text = "\n".join(pages)
    
    with open(temp_text_path, 'w', encoding='utf-8') as f:
        f.write(full_text)
        
    print(f"Successfully extracted text to '{temp_text_path}'.")
    return True

def analyze_text_for_rules(tender_text_path, prompt_template_path, output_json_path):
    """Analyzes the extracted text to get scoring rules using AI."""
    try:
        with open(tender_text_path, 'r', encoding='utf-8') as f:
            tender_text = f.read()
        with open(prompt_template_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError as e:
        print(f"Error: Could not find a necessary file. Details: {e}")
        return

    prompt = prompt_template.replace('{TENDER_TEXT_PLACEHOLDER}', tender_text)

    print("Connecting to AI model...")
    analyzer = LocalAIAnalyzer()
    ai_response = analyzer.analyze_text(prompt)

    if "Error: Could not connect" in ai_response:
        print(ai_response)
        return

    print("AI response received. Cleaning and validating JSON...")
    clean_response = ai_response.strip()
    if clean_response.startswith('```json'):
        clean_response = clean_response[7:]
    if clean_response.endswith('```'):
        clean_response = clean_response[:-3]
    clean_response = clean_response.strip()

    try:
        parsed_json = json.loads(clean_response)
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, ensure_ascii=False, indent=2)
        print(f"Scoring rules successfully saved to {output_json_path}.")
        
        print("\n--- Extracted Scoring Rules ---")
        print(json.dumps(parsed_json, ensure_ascii=False, indent=2))

    except json.JSONDecodeError:
        print("Error: AI response was not valid JSON after cleaning.")
        print("--- Raw AI Response ---")
        print(ai_response)

def main():
    tender_pdf_path = r'D:\user\PythonProject\AI_env2\uploads\1_tender_招标文件正文.pdf'
    temp_text_path = 'tender_text.tmp'
    prompt_template_path = 'prompt.txt'
    output_json_path = 'scoring_rules.json'

    # Step 1: Extract text from PDF
    if not extract_and_save_text(tender_pdf_path, temp_text_path):
        return # Stop if extraction fails

    # Step 2: Analyze text for rules
    analyze_text_for_rules(temp_text_path, prompt_template_path, output_json_path)
    
    # Clean up the temporary text file
    if os.path.exists(temp_text_path):
        os.remove(temp_text_path)
        print(f"\nCleaned up temporary file: {temp_text_path}")


if __name__ == '__main__':
    main()
