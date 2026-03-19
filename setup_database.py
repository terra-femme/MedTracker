"""
Setup Script for MedTracker Database (Enhanced Version)
This script will:
1. Create the database tables if they don't exist
2. Add sample medications for testing (with all new fields!)
3. Show you what's in the database

USAGE:
    python setup_database.py

NOTE: Run this from your MedTracker project root directory!
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
    print("\nTry: cd MedTracker && python setup_database.py")
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
    """Add sample medications for testing - ENHANCED VERSION with all new fields!"""
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
        
        # =================================================================
        # SAMPLE MEDICATIONS - Now with ALL enhanced fields!
        # =================================================================
        # These represent realistic medication scenarios you might encounter
        # in a health-tech application
        # =================================================================
        
        sample_meds = [
            {
                # Common blood pressure medication
                "name": "Lisinopril",
                "rxcui": "314076",  # Real RxCUI from RxNorm!
                "form_type": "Tablet",
                "strength": 10.0,
                "strength_unit": "mg",
                "method_of_intake": "Orally",
                "dosage": "10 mg",  # Backward compatible field
                "quantity": 1.0,
                "quantity_unit": "tablet(s)",
                "when_to_take": "Any Time",
                "frequency": "Once daily",
                "start_date": date.today(),
                "end_date": None,
                "is_long_term": True,  # Blood pressure meds are usually long-term
                "is_active": True,
                "notes": "Take in the morning. Monitor blood pressure weekly.",
                "taken_for": "High Blood Pressure"
            },
            {
                # Diabetes medication
                "name": "Metformin",
                "rxcui": "861004",
                "form_type": "Tablet",
                "strength": 500.0,
                "strength_unit": "mg",
                "method_of_intake": "Orally",
                "dosage": "500 mg",
                "quantity": 1.0,
                "quantity_unit": "tablet(s)",
                "when_to_take": "With Food",  # Important! Metformin should be taken with meals
                "frequency": "Twice daily",
                "start_date": date.today(),
                "end_date": None,
                "is_long_term": True,
                "is_active": True,
                "notes": "Take with breakfast and dinner to reduce stomach upset.",
                "taken_for": "Type 2 Diabetes"
            },
            {
                # Pain reliever (short-term)
                "name": "Ibuprofen",
                "rxcui": "310965",
                "form_type": "Tablet",
                "strength": 400.0,
                "strength_unit": "mg",
                "method_of_intake": "Orally",
                "dosage": "400 mg",
                "quantity": 1.0,
                "quantity_unit": "tablet(s)",
                "when_to_take": "After Food",  # NSAIDs can upset stomach
                "frequency": "As needed",
                "start_date": date.today(),
                "end_date": None,
                "is_long_term": False,  # Short-term use
                "is_active": True,
                "notes": "For back pain. Do not exceed 1200mg per day.",
                "taken_for": "Pain Relief"
            },
            {
                # Vitamin supplement
                "name": "Vitamin D3",
                "rxcui": "636676",
                "form_type": "Capsule",
                "strength": 1000.0,
                "strength_unit": "IU",
                "method_of_intake": "Orally",
                "dosage": "1000 IU",
                "quantity": 1.0,
                "quantity_unit": "capsule(s)",
                "when_to_take": "With Food",  # Fat-soluble vitamin absorbs better with food
                "frequency": "Every morning",
                "start_date": date.today(),
                "end_date": None,
                "is_long_term": True,
                "is_active": True,
                "notes": "Take with breakfast for better absorption.",
                "taken_for": "Vitamin Deficiency"
            },
            {
                # Cholesterol medication
                "name": "Atorvastatin",
                "rxcui": "617312",
                "form_type": "Tablet",
                "strength": 20.0,
                "strength_unit": "mg",
                "method_of_intake": "Orally",
                "dosage": "20 mg",
                "quantity": 1.0,
                "quantity_unit": "tablet(s)",
                "when_to_take": "At Bedtime",  # Statins work best at night
                "frequency": "Every night",
                "start_date": date.today(),
                "end_date": None,
                "is_long_term": True,
                "is_active": True,
                "notes": "Take at bedtime. Avoid grapefruit juice.",
                "taken_for": "High Cholesterol"
            },
            {
                # Inhaler (different form type)
                "name": "Albuterol",
                "rxcui": "745679",
                "form_type": "Inhaler",
                "strength": 90.0,
                "strength_unit": "mcg",
                "method_of_intake": "Inhaled",
                "dosage": "90 mcg/puff",
                "quantity": 2.0,
                "quantity_unit": "puff(s)",
                "when_to_take": "Any Time",
                "frequency": "As needed",
                "start_date": date.today(),
                "end_date": None,
                "is_long_term": True,
                "is_active": True,
                "notes": "Use for shortness of breath. Shake well before use.",
                "taken_for": "Asthma"
            },
            {
                # Eye drops (different method of intake)
                "name": "Latanoprost",
                "rxcui": "1116632",
                "form_type": "Drops",
                "strength": 0.005,
                "strength_unit": "%",
                "method_of_intake": "Ocular",
                "dosage": "0.005%",
                "quantity": 1.0,
                "quantity_unit": "drop(s)",
                "when_to_take": "At Bedtime",
                "frequency": "Every night",
                "start_date": date.today(),
                "end_date": None,
                "is_long_term": True,
                "is_active": True,
                "notes": "One drop in each eye at bedtime. Remove contact lenses first.",
                "taken_for": "Glaucoma"
            },
            {
                # Inactive medication (for testing filters)
                "name": "Amoxicillin",
                "rxcui": "308182",
                "form_type": "Capsule",
                "strength": 500.0,
                "strength_unit": "mg",
                "method_of_intake": "Orally",
                "dosage": "500 mg",
                "quantity": 1.0,
                "quantity_unit": "capsule(s)",
                "when_to_take": "Any Time",
                "frequency": "Three times daily",
                "start_date": date(2024, 11, 1),  # Started in the past
                "end_date": date(2024, 11, 10),   # Already ended
                "is_long_term": False,
                "is_active": False,  # INACTIVE - course completed
                "notes": "Antibiotic course completed. Full 10-day course taken.",
                "taken_for": "Bacterial Infection"
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
        print("\n📋 Medications added:")
        for med in sample_meds:
            status = "🟢 Active" if med["is_active"] else "⚪ Inactive"
            print(f"   • {med['name']} ({med['dosage']}) - {med['taken_for']} [{status}]")
        
    except Exception as e:
        print(f"❌ Error adding sample data: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def show_current_data():
    """Display all medications in the database with enhanced details"""
    print("\n" + "=" * 70)
    print("📋 CURRENT MEDICATIONS IN DATABASE")
    print("=" * 70)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        medications = db.query(Medication).all()
        
        if not medications:
            print("\n❌ No medications found in database!")
            print("   Run this script again and choose to add sample data.")
        else:
            active_count = sum(1 for m in medications if m.is_active)
            inactive_count = len(medications) - active_count
            
            print(f"\n📊 Summary: {active_count} active, {inactive_count} inactive\n")
            
            for i, med in enumerate(medications, 1):
                # Status indicator
                if med.is_active:
                    status = "🟢 ACTIVE"
                    status_color = ""
                else:
                    status = "⚪ INACTIVE"
                    status_color = "(completed/stopped)"
                
                print(f"\n{'─' * 70}")
                print(f"  {i}. {med.name} {status} {status_color}")
                print(f"{'─' * 70}")
                
                # Basic info
                print(f"     💊 Form: {med.form_type or 'Not specified'}")
                print(f"     💪 Strength: {med.strength} {med.strength_unit}" if med.strength else "     💪 Strength: Not specified")
                print(f"     📏 Dose: {med.quantity} {med.quantity_unit}" if med.quantity else "     📏 Dose: Not specified")
                print(f"     🕐 Frequency: {med.frequency}")
                print(f"     🍽️  When: {med.when_to_take or 'Any time'}")
                print(f"     💉 Method: {med.method_of_intake or 'Not specified'}")
                
                # Medical context
                if med.taken_for:
                    print(f"     🏥 Condition: {med.taken_for}")
                
                # Duration
                duration = "Long-term" if med.is_long_term else "Short-term"
                print(f"     📅 Duration: {duration}")
                print(f"     📅 Started: {med.start_date}")
                if med.end_date:
                    print(f"     📅 Ended: {med.end_date}")
                
                # Notes
                if med.notes:
                    print(f"     📝 Notes: {med.notes}")
                
                # RxCUI (for interoperability)
                if med.rxcui:
                    print(f"     🔗 RxCUI: {med.rxcui}")
        
        print("\n" + "=" * 70)
        print(f"📊 Total: {len(medications)} medications")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def add_sample_logs():
    """Add sample medication logs for testing adherence features"""
    print("\n📝 Adding sample medication logs...")
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Get active medications
        medications = db.query(Medication).filter(Medication.is_active == True).all()
        
        if not medications:
            print("⚠️  No active medications found. Add medications first.")
            return
        
        from datetime import timedelta
        import random
        
        logs_added = 0
        today = datetime.now()
        
        # Add logs for the past 7 days
        for med in medications[:3]:  # Just first 3 active meds
            for days_ago in range(7):
                log_date = today - timedelta(days=days_ago)
                
                # 80% chance of taking medication (realistic adherence)
                was_taken = random.random() < 0.8
                
                log = MedicationLog(
                    medication_id=med.id,
                    taken_at=log_date,
                    was_taken=was_taken,
                    notes="Auto-generated test data" if not was_taken else None
                )
                db.add(log)
                logs_added += 1
        
        db.commit()
        print(f"✅ Added {logs_added} sample logs for adherence testing!")
        
    except Exception as e:
        print(f"❌ Error adding logs: {e}")
        db.rollback()
    finally:
        db.close()


def add_sample_reminders():
    """Add sample reminders for testing"""
    print("\n⏰ Adding sample reminders...")
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        from datetime import time as dt_time
        
        # Get active medications
        medications = db.query(Medication).filter(Medication.is_active == True).all()
        
        if not medications:
            print("⚠️  No active medications found. Add medications first.")
            return
        
        reminders_added = 0
        
        # Define reminder times based on frequency
        reminder_times = {
            "Once daily": [dt_time(8, 0)],
            "Twice daily": [dt_time(8, 0), dt_time(20, 0)],
            "Three times daily": [dt_time(8, 0), dt_time(14, 0), dt_time(20, 0)],
            "Every morning": [dt_time(8, 0)],
            "Every night": [dt_time(21, 0)],
        }
        
        for med in medications:
            times = reminder_times.get(med.frequency, [])
            
            for reminder_time in times:
                # Check if reminder already exists
                existing = db.query(Reminder).filter(
                    Reminder.medication_id == med.id,
                    Reminder.reminder_time == reminder_time
                ).first()
                
                if not existing:
                    reminder = Reminder(
                        medication_id=med.id,
                        reminder_time=reminder_time,
                        is_sent=False
                    )
                    db.add(reminder)
                    reminders_added += 1
        
        db.commit()
        print(f"✅ Added {reminders_added} sample reminders!")
        
    except Exception as e:
        print(f"❌ Error adding reminders: {e}")
        db.rollback()
    finally:
        db.close()


def check_database_file():
    """Check if database file exists"""
    import os
    db_exists = os.path.exists('medtracker.db')
    
    if db_exists:
        size = os.path.getsize('medtracker.db')
        print(f"✅ Database file exists (Size: {size:,} bytes)")
    else:
        print("⚠️  Database file doesn't exist yet - will be created")
    
    return db_exists


def main():
    """Main setup function"""
    print("=" * 70)
    print("🏥 MedTracker Database Setup (Enhanced Version)")
    print("=" * 70)
    
    # Check if database file exists
    check_database_file()
    
    # Create tables
    if not setup_database():
        print("\n❌ Setup failed!")
        return
    
    # Menu
    print("\n" + "=" * 70)
    print("What would you like to do?\n")
    print("  1. Add sample medications only")
    print("  2. Add sample medications + logs + reminders (full test data)")
    print("  3. Just show current data")
    print("  4. Exit")
    print("")
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == '1':
        add_sample_data()
    elif choice == '2':
        add_sample_data()
        add_sample_logs()
        add_sample_reminders()
    elif choice == '3':
        pass  # Just show data
    elif choice == '4':
        print("\n👋 Goodbye!")
        return
    else:
        print("⚠️  Invalid choice, showing current data...")
    
    # Show current data
    show_current_data()
    
    print("\n" + "=" * 70)
    print("✅ Setup complete!")
    print("\n📍 Next steps:")
    print("   1. Start your FastAPI server: uvicorn main:app --reload")
    print("   2. Open browser: http://localhost:8000")
    print("   3. You should see your medications!")
    print("=" * 70)


def add_pill_columns():
    """
    Safe migration: add pill_shape, pill_color, pill_size to medications table.
    Uses raw SQLite so it works even when SQLAlchemy doesn't know about the columns yet.
    No-op if the columns already exist.
    """
    import sqlite3, os
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./medtracker.db")
    db_path = db_path.replace("sqlite:///./", "").replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return  # DB not created yet; create_all will add columns on first run
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    existing = {row[1] for row in cur.execute("PRAGMA table_info(medications)")}
    for col, typedef in [
        ("pill_shape", "VARCHAR"),
        ("pill_color", "VARCHAR"),
        ("pill_size",  "VARCHAR"),
    ]:
        if col not in existing:
            cur.execute(f"ALTER TABLE medications ADD COLUMN {col} {typedef}")
            print(f"✅ Added column: {col}")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    add_pill_columns()
    main()
