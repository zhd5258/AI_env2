from modules.database import SessionLocal, TenderProject
from modules.price_score_calculator import PriceScoreCalculator

def update_price_scores():
    db = SessionLocal()
    try:
        # Get all projects
        projects = db.query(TenderProject).all()
        print(f"Total projects: {len(projects)}")
        
        calculator = PriceScoreCalculator(db_session=db)
        
        for project in projects:
            print(f"\nProcessing project ID: {project.id}")
            try:
                # Calculate price scores
                price_scores = calculator.calculate_project_price_scores(project.id)
                
                if price_scores:
                    print(f"  Successfully calculated price scores for project {project.id}:")
                    for bidder, score in price_scores.items():
                        print(f"    {bidder}: {score}")
                else:
                    print(f"  No price scores calculated for project {project.id}")
                    
            except Exception as e:
                print(f"  Error processing project {project.id}: {e}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    update_price_scores()