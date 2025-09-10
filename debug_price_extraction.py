from modules.database import SessionLocal, AnalysisResult
import json

def debug_price_extraction():
    db = SessionLocal()
    try:
        # Check the latest analysis results for price information
        results = db.query(AnalysisResult).all()
        print(f"Total analysis results: {len(results)}")
        
        for result in results[-3:]:  # Check the latest 3 results
            print(f"\n--- Analysis Result ID: {result.id} ---")
            print(f"Bidder: {result.bidder_name}")
            print(f"Price Score (from field): {result.price_score}")
            print(f"Extracted Price: {result.extracted_price}")
            
            # Check detailed scores for price-related items
            detailed_scores = result.detailed_scores
            if isinstance(detailed_scores, str):
                detailed_scores = json.loads(detailed_scores)
                
            def find_price_items(scores, level=0):
                indent = "  " * level
                if not isinstance(scores, list):
                    return
                    
                for item in scores:
                    criteria_name = item.get('criteria_name', '')
                    is_price_related = any(keyword in criteria_name for keyword in ['价格', '报价', 'Price', 'price'])
                    is_marked_price = item.get('is_price_criteria', False)
                    
                    if is_price_related or is_marked_price:
                        print(f"{indent}PRICE ITEM: {criteria_name}")
                        print(f"{indent}  Score: {item.get('score', 'N/A')}")
                        print(f"{indent}  Extracted Price: {item.get('extracted_price', 'N/A')}")
                        print(f"{indent}  Is Price Criteria: {is_marked_price}")
                    
                    children = item.get('children', [])
                    if children:
                        find_price_items(children, level + 1)
            
            print("Searching for price-related items in detailed scores:")
            find_price_items(detailed_scores)
            
    except Exception as e:
        print(f"Error debugging price extraction: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    debug_price_extraction()