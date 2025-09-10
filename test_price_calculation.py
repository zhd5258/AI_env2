from modules.database import SessionLocal
from modules.price_score_calculator import PriceScoreCalculator

def test_price_calculation():
    db = SessionLocal()
    try:
        # Test price calculation for the latest project
        calculator = PriceScoreCalculator(db_session=db)
        
        # Find the latest project with completed analysis results
        from modules.database import TenderProject, AnalysisResult
        from sqlalchemy import desc
        
        latest_project = db.query(TenderProject).order_by(desc(TenderProject.id)).first()
        if not latest_project:
            print("No projects found")
            return
            
        print(f"Testing price calculation for project ID: {latest_project.id}")
        
        # Calculate price scores
        price_scores = calculator.calculate_project_price_scores(latest_project.id)
        print(f"Calculated price scores: {price_scores}")
        
        if price_scores:
            print("Price calculation successful!")
            print("Price scores by bidder:")
            for bidder, score in price_scores.items():
                print(f"  {bidder}: {score}")
        else:
            print("No price scores calculated")
            
    except Exception as e:
        print(f"Error testing price calculation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_price_calculation()