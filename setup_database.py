"""
Setup Script for MedTracker Database
This script will:
1. Create the database tables if they don't exist
2. Add sample medications for testing
3. Show you what's in the database
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date
import sys

# Import your models
try:
    from backend.database import Base, engine, get_db
    from backend.models import Medication, MedicationLog, Reminder
    print("✅ Successfully imported database models")
except ImportError as e:
    print(f"❌ Error importing models: {e}")
    print("Make sure you're running this from your project root directory!")
    sys.exit(1)

def setup_database():
    """Create all database tables"""
    print("\n📊 Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

def add_sample_data():
    """Add sample medications for testing"""
    print("\n💊 Adding sample medications...")
    
    # Create a session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if we already have data
        existing_count = db.query(Medication).count()
        if existing_count > 0:
            print(f"ℹ️  Database already has {existing_count} medications")
            choice = input("Do you want to add more sample data? (y/n): ")
            if choice.lower() != 'y':
                print("Skipping sample data...")
                return
        
        # Sample medications
        sample_meds = [
            {
                "name": "Aspirin",
                "dosage": "500mg",
                "frequency": "Twice daily",
                "start_date": date.today(),
                "is_active": True,
                "notes": "Take with food"
            },
            {
                "name": "Metformin",
                "dosage": "850mg",
                "frequency": "Three times daily",
                "start_date": date.today(),
                "is_active": True,
                "notes": "With meals"
            },
            {
                "name": "Lisinopril",
                "dosage": "10mg",
                "frequency": "Once daily",
                "start_date": date.today(),
                "is_active": True,
                "notes": "In the morning"
            },
            {
                "name": "Vitamin D",
                "dosage": "1000 IU",
                "frequency": "Every morning",
                "start_date": date.today(),
                "is_active": True,
                "notes": None
            }
        ]
        
        # Add medications to database
        added = 0
        for med_data in sample_meds:
            med = Medication(**med_data)
            db.add(med)
            added += 1
        
        db.commit()
        print(f"✅ Added {added} sample medications!")
        
    except Exception as e:
        print(f"❌ Error adding sample data: {e}")
        db.rollback()
    finally:
        db.close()

def show_current_data():
    """Display all medications in the database"""
    print("\n📋 Current medications in database:")
    print("=" * 60)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        medications = db.query(Medication).all()
        
        if not medications:
            print("❌ No medications found in database!")
            print("   Run this script again and choose to add sample data.")
        else:
            for i, med in enumerate(medications, 1):
                status = "✅ Active" if med.is_active else "❌ Inactive"
                print(f"\n{i}. {med.name} ({status})")
                print(f"   Dosage: {med.dosage}")
                print(f"   Frequency: {med.frequency}")
                print(f"   Start Date: {med.start_date}")
                if med.notes:
                    print(f"   Notes: {med.notes}")
        
        print("\n" + "=" * 60)
        print(f"Total medications: {len(medications)}")
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
    finally:
        db.close()

def check_database_file():
    """Check if database file exists"""
    import os
    db_exists = os.path.exists('medtracker.db')
    
    if db_exists:
        size = os.path.getsize('medtracker.db')
        print(f"✅ Database file exists (Size: {size} bytes)")
    else:
        print("⚠️  Database file doesn't exist yet - will be created")
    
    return db_exists

def main():
    """Main setup function"""
    print("=" * 60)
    print("🏥 MedTracker Database Setup")
    print("=" * 60)
    
    # Check if database file exists
    check_database_file()
    
    # Create tables
    if not setup_database():
        print("\n❌ Setup failed!")
        return
    
    # Ask if user wants to add sample data
    print("\n" + "=" * 60)
    add_sample = input("Do you want to add sample medications? (y/n): ")
    if add_sample.lower() == 'y':
        add_sample_data()
    
    # Show current data
    show_current_data()
    
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("\n📝 Next steps:")
    print("1. Start your FastAPI server: uvicorn main:app --reload")
    print("2. Open browser: http://localhost:8000")
    print("3. You should see your medications!")
    print("=" * 60)

if __name__ == "__main__":
    main()
