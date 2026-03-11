"""
AdherenceAgent - Calculates medication adherence statistics

Responsibilities:
- Calculate daily/weekly/monthly adherence rates
- Track missed vs taken doses
- Generate adherence reports by medication

Does NOT:
- Handle scheduling (ScheduleAgent)
- Manage medications (MedicationAgent)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AdherenceReport:
    period_start: date
    period_end: date
    overall_rate: float  # 0-100
    total_expected: int
    total_taken: int
    total_missed: int
    by_medication: List[Dict]
    daily_breakdown: List[Dict]


class AdherenceAgent:
    """
    Agent for calculating adherence statistics
    
    Usage:
        agent = AdherenceAgent(db_session)
        report = agent.calculate_weekly_adherence()
        rate = agent.get_medication_adherence(med_id, days=30)
    """
    
    def __init__(self, db_session):
        self.db = db_session
    
    def calculate_adherence(self, days: int = 7, 
                           end_date: Optional[date] = None) -> AdherenceReport:
        """
        Calculate adherence for a given period
        
        Args:
            days: Number of days to look back
            end_date: End date (default: today)
            
        Returns:
            AdherenceReport with all statistics
        """
        if end_date is None:
            end_date = date.today()
        
        start_date = end_date - timedelta(days=days-1)
        
        # Get active medications for the period
        medications = self._get_active_medications(start_date, end_date)
        
        # Get all logs for the period
        logs = self._get_logs(start_date, end_date)
        
        # Calculate expected doses per day
        daily_expected = self._calculate_daily_expected(medications, start_date, end_date)
        
        # Calculate actual doses taken per day
        daily_taken = self._calculate_daily_taken(logs, start_date, end_date)
        
        # Build daily breakdown
        daily_breakdown = []
        total_expected = 0
        total_taken = 0
        
        for day_offset in range(days):
            check_date = start_date + timedelta(days=day_offset)
            expected = daily_expected.get(check_date, 0)
            taken = daily_taken.get(check_date, 0)
            missed = expected - taken
            
            effective_taken = min(taken, expected)
            rate = (effective_taken / expected * 100) if expected > 0 else 100.0

            daily_breakdown.append({
                "date": check_date.isoformat(),
                "day_name": check_date.strftime("%a"),
                "expected": expected,
                "taken": effective_taken,
                "missed": max(0, expected - effective_taken),
                "rate": round(rate, 1)
            })

            total_expected += expected
            total_taken += effective_taken

        # Calculate overall rate
        overall_rate = (total_taken / total_expected * 100) if total_expected > 0 else 0.0
        
        # Calculate per-medication adherence
        by_medication = self._calculate_by_medication(medications, logs, start_date, end_date)
        
        return AdherenceReport(
            period_start=start_date,
            period_end=end_date,
            overall_rate=round(overall_rate, 1),
            total_expected=total_expected,
            total_taken=total_taken,
            total_missed=total_expected - total_taken,
            by_medication=by_medication,
            daily_breakdown=daily_breakdown
        )
    
    def calculate_streak(self, threshold: float = 80.0) -> int:
        """
        Calculate current adherence streak
        
        A "good day" = adherence >= threshold (default 80%)
        Streak = consecutive good days ending today
        
        Returns:
            Number of consecutive good days
        """
        # Get last 30 days of data
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        medications = self._get_active_medications(start_date, end_date)
        logs = self._get_logs(start_date, end_date)
        
        daily_expected = self._calculate_daily_expected(medications, start_date, end_date)
        daily_taken = self._calculate_daily_taken(logs, start_date, end_date)
        
        streak = 0
        current_date = end_date
        
        while current_date >= start_date:
            expected = daily_expected.get(current_date, 0)
            taken = daily_taken.get(current_date, 0)
            
            if expected == 0:
                # No medications expected this day, skip
                current_date -= timedelta(days=1)
                continue
            
            rate = (taken / expected * 100)
            
            if rate >= threshold:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    def get_today_summary(self) -> Dict:
        """Get today's adherence summary"""
        today = date.today()
        
        # Get active medications
        medications = self._get_active_medications(today, today)
        
        # Calculate expected doses today
        daily_expected = self._calculate_daily_expected(medications, today, today)
        expected = daily_expected.get(today, 0)
        
        # Get today's logs
        logs = self._get_logs(today, today)
        daily_taken = self._calculate_daily_taken(logs, today, today)
        taken = daily_taken.get(today, 0)
        
        return {
            "date": today.isoformat(),
            "expected": expected,
            "taken": taken,
            "missed": max(0, expected - taken),
            "rate": round((taken / expected * 100), 1) if expected > 0 else 0.0,
            "complete": taken >= expected and expected > 0
        }
    
    def _get_active_medications(self, start_date: date, end_date: date) -> List[Dict]:
        """Get medications active during the date range"""
        from backend.models import Medication as MedicationModel
        
        db_meds = self.db.query(MedicationModel).filter(
            MedicationModel.is_active == True,
            MedicationModel.start_date <= end_date
        ).all()
        
        return [
            {
                "id": m.id,
                "name": m.name,
                "frequency": m.frequency,
                "start_date": m.start_date,
                "reminder_times": [str(r.reminder_time)[:5] for r in m.reminders if r.is_active]
            }
            for m in db_meds
        ]
    
    def _get_logs(self, start_date: date, end_date: date) -> List[Dict]:
        """Get medication logs for date range"""
        from backend.models import MedicationLog as LogModel
        
        start = datetime.combine(start_date, time.min)
        end = datetime.combine(end_date, time.max)
        
        db_logs = self.db.query(LogModel).filter(
            LogModel.taken_at >= start,
            LogModel.taken_at <= end,
            LogModel.was_taken == True
        ).all()
        
        return [
            {
                "medication_id": log.medication_id,
                "taken_at": log.taken_at,
                "date": log.taken_at.date()
            }
            for log in db_logs
        ]
    
    def _calculate_daily_expected(self, medications: List[Dict], 
                                   start_date: date, end_date: date) -> Dict[date, int]:
        """Calculate expected doses per day"""
        daily_expected = defaultdict(int)
        
        frequency_multiplier = {
            'once_daily': 1,
            'twice_daily': 2,
            'three_times_daily': 3,
            'every_morning': 1,
            'every_night': 1,
        }
        
        current_date = start_date
        while current_date <= end_date:
            for med in medications:
                # Check if medication was active on this date
                if med.get('start_date') and med['start_date'] > current_date:
                    continue
                
                # Count expected doses based on reminder times
                reminder_times = med.get('reminder_times', [])
                if reminder_times:
                    daily_expected[current_date] += len(reminder_times)
                else:
                    # Fallback to frequency
                    freq = med.get('frequency', 'once_daily')
                    mult = frequency_multiplier.get(freq, 1)
                    daily_expected[current_date] += mult
            
            current_date += timedelta(days=1)
        
        return dict(daily_expected)
    
    def _calculate_daily_taken(self, logs: List[Dict], 
                                start_date: date, end_date: date) -> Dict[date, int]:
        """Calculate actual doses taken per day"""
        daily_taken = defaultdict(int)
        
        for log in logs:
            log_date = log.get('date')
            if log_date and start_date <= log_date <= end_date:
                daily_taken[log_date] += 1
        
        return dict(daily_taken)
    
    def _calculate_by_medication(self, medications: List[Dict], logs: List[Dict],
                                  start_date: date, end_date: date) -> List[Dict]:
        """Calculate adherence per medication"""
        days = (end_date - start_date).days + 1
        
        result = []
        for med in medications:
            med_id = med['id']
            
            # Count expected (based on reminder times * days)
            reminder_times = med.get('reminder_times', [])
            if reminder_times:
                expected = len(reminder_times) * days
            else:
                freq_mult = {'once_daily': 1, 'twice_daily': 2, 'three_times_daily': 3}
                expected = freq_mult.get(med.get('frequency'), 1) * days
            
            # Count taken, capped at expected to prevent rates above 100%
            taken = min(
                sum(1 for log in logs if log['medication_id'] == med_id),
                expected
            )

            rate = (taken / expected * 100) if expected > 0 else 0.0
            
            result.append({
                "id": med_id,
                "name": med['name'],
                "expected": expected,
                "taken": taken,
                "missed": max(0, expected - taken),
                "adherence": round(rate, 1)
            })
        
        # Sort by adherence (lowest first - most concerning)
        result.sort(key=lambda x: x['adherence'])
        
        return result
    
    def format_report(self, report: AdherenceReport) -> Dict:
        """Convert report to JSON-serializable dict"""
        return {
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "overall_rate": report.overall_rate,
            "total_expected": report.total_expected,
            "total_taken": report.total_taken,
            "total_missed": report.total_missed,
            "daily_breakdown": report.daily_breakdown,
            "by_medication": report.by_medication
        }
