import json
from modules.database import SessionLocal, AnalysisResult, TenderProject, BidDocument

def check_detailed_db_status():
    db = SessionLocal()
    try:
        # Check projects
        projects = db.query(TenderProject).all()
        print(f"Total projects: {len(projects)}")
        for project in projects:
            print(f"  Project ID: {project.id}, Code: {project.project_code}, Status: {project.status}")
            
            # Check bid documents for this project
            bid_docs = db.query(BidDocument).filter(BidDocument.project_id == project.id).all()
            print(f"  Bid documents: {len(bid_docs)}")
            for doc in bid_docs:
                print(f"    Bid ID: {doc.id}, Bidder: {doc.bidder_name}, Status: {doc.processing_status}")
                
                # Check analysis result for this bid document
                analysis_result = db.query(AnalysisResult).filter(AnalysisResult.bid_document_id == doc.id).first()
                if analysis_result:
                    print(f"      Analysis Result ID: {analysis_result.id}")
                    print(f"      Total Score: {analysis_result.total_score}")
                    print(f"      Price Score: {analysis_result.price_score}")
                    print(f"      Extracted Price: {analysis_result.extracted_price}")
                    
                    # Check detailed scores structure
                    detailed = json.loads(analysis_result.detailed_scores) if isinstance(analysis_result.detailed_scores, str) else analysis_result.detailed_scores
                    
                    def print_scores_structure(scores, level=0):
                        indent = "  " * (level + 2)
                        if isinstance(scores, list):
                            for item in scores:
                                criteria_name = item.get('criteria_name', 'N/A')
                                score = item.get('score', 'N/A')
                                is_price = item.get('is_price_criteria', False)
                                print(f"{indent}{criteria_name}: {score} {'(PRICE)' if is_price else ''}")
                                children = item.get('children', [])
                                if children:
                                    print_scores_structure(children, level + 1)
                    
                    print("      Detailed scores structure:")
                    print_scores_structure(detailed)
                else:
                    print("      No analysis result found")
                    
    except Exception as e:
        print(f"Error checking database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_detailed_db_status()