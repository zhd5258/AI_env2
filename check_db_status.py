import json
from modules.database import SessionLocal, AnalysisResult

def check_db_status():
    db = SessionLocal()
    try:
        results = db.query(AnalysisResult).all()
        print(f"Total analysis results: {len(results)}")
        
        if results:
            result = results[-1]  # Get the latest result
            print(f"Latest result ID: {result.id}")
            print(f"Bidder: {result.bidder_name}")
            print(f"Price Score: {result.price_score}")
            print(f"Extracted Price: {result.extracted_price}")
            
            # Check detailed scores
            detailed = json.loads(result.detailed_scores) if isinstance(result.detailed_scores, str) else result.detailed_scores
            print("First few detailed scores:")
            if isinstance(detailed, list):
                for item in detailed[:3]:
                    print(f"  {item.get('criteria_name', 'N/A')}: {item.get('score', 'N/A')}")
            
            # Check if there are any price-related criteria
            def find_price_criteria(scores):
                if not isinstance(scores, list):
                    return None
                    
                for item in scores:
                    criteria_name = item.get('criteria_name', '').lower()
                    is_price = any(keyword in criteria_name for keyword in ['价格', 'price', '报价', '投标报价']) or item.get('is_price_criteria', False)
                    if is_price:
                        return item
                    
                    # Check children recursively
                    children = item.get('children', [])
                    if children:
                        child_result = find_price_criteria(children)
                        if child_result:
                            return child_result
                return None
            
            price_item = find_price_criteria(detailed)
            if price_item:
                print(f"Found price criteria: {price_item.get('criteria_name')}")
                print(f"Price item score: {price_item.get('score')}")
                print(f"Is price criteria: {price_item.get('is_price_criteria', False)}")
            else:
                print("No price criteria found in detailed scores")
        else:
            print("No analysis results found")
            
    except Exception as e:
        print(f"Error checking database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db_status()