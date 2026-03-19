"""
StreakAgent - Manages adherence streaks and achievements

Responsibilities:
- Calculate current adherence streak
- Track best streaks (all-time, weekly, monthly)
- Award achievements for milestones
- Handle streak breaks and restarts
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class StreakInfo:
    current_streak: int  # Current consecutive good days
    best_streak: int  # All-time best
    weekly_best: int  # Best this week
    monthly_best: int  # Best this month
    last_good_day: Optional[date]  # Last day with 100% adherence
    streak_at_risk: bool  # Is current streak at risk today?


class StreakAgent:
    """
    Agent for managing adherence streaks
    
    Usage:
        agent = StreakAgent(adherence_agent)
        streak = agent.get_current_streak()
        if streak.streak_at_risk:
            send_reminder_to_user()
    """
    
    # Thresholds
    GOOD_DAY_THRESHOLD = 80.0  # 80% adherence = good day
    STREAK_AT_RISK_HOUR = 20  # 8 PM - if not complete by now, streak at risk
    
    def __init__(self, adherence_agent):
        self.adherence = adherence_agent
    
    def get_streak_info(self) -> StreakInfo:
        """Get complete streak information"""
        current = self._calculate_current_streak()
        best = self._get_best_streak()
        weekly = self._get_weekly_best()
        monthly = self._get_monthly_best()
        last_good = self._get_last_good_day()
        at_risk = self._is_streak_at_risk()
        
        return StreakInfo(
            current_streak=current,
            best_streak=best,
            weekly_best=weekly,
            monthly_best=monthly,
            last_good_day=last_good,
            streak_at_risk=at_risk
        )
    
    def get_current_streak(self) -> int:
        """Get current consecutive good days"""
        return self._calculate_current_streak()
    
    def check_streak_status(self) -> Dict:
        """
        Check current streak status and provide feedback
        
        Returns:
            {
                "status": "active" | "at_risk" | "broken",
                "streak": int,
                "message": str,
                "action_needed": bool
            }
        """
        streak = self._calculate_current_streak()
        at_risk = self._is_streak_at_risk()
        today_summary = self.adherence.get_today_summary()
        
        if today_summary["complete"]:
            return {
                "status": "active",
                "streak": streak,
                "message": f"🔥 {streak} day streak! Great job!",
                "action_needed": False
            }
        elif at_risk:
            remaining = today_summary["expected"] - today_summary["taken"]
            return {
                "status": "at_risk",
                "streak": streak,
                "message": f"⚠️ Streak at risk! {remaining} doses remaining today.",
                "action_needed": True
            }
        else:
            remaining = today_summary["expected"] - today_summary["taken"]
            if remaining > 0:
                return {
                    "status": "active",
                    "streak": streak,
                    "message": f"📅 {remaining} doses left today to maintain your streak.",
                    "action_needed": False
                }
            else:
                return {
                    "status": "active",
                    "streak": streak,
                    "message": f"✅ All caught up! Keep it going!",
                    "action_needed": False
                }
    
    def get_milestones(self) -> List[Dict]:
        """Get upcoming streak milestones"""
        current = self._calculate_current_streak()
        
        milestones = [7, 14, 30, 60, 90, 180, 365]
        upcoming = []
        
        for milestone in milestones:
            if current < milestone:
                days_left = milestone - current
                upcoming.append({
                    "milestone": milestone,
                    "days_left": days_left,
                    "reward": self._get_milestone_reward(milestone)
                })
        
        return upcoming
    
    def _calculate_current_streak(self) -> int:
        """Calculate current consecutive good days"""
        from datetime import datetime
        
        streak = 0
        check_date = date.today()
        
        # Check up to 365 days back
        for _ in range(365):
            # Get adherence for this day
            day_report = self.adherence.calculate_adherence(days=1, end_date=check_date)
            
            if day_report.total_expected == 0:
                # No medications expected, skip this day
                check_date -= timedelta(days=1)
                continue
            
            rate = day_report.overall_rate
            
            if rate >= self.GOOD_DAY_THRESHOLD:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    def _get_best_streak(self) -> int:
        """Get all-time best streak"""
        # This would query a stored value in a full implementation
        # For now, calculate from last 90 days
        return self._calculate_best_in_range(90)
    
    def _get_weekly_best(self) -> int:
        """Get best streak this week"""
        return self._calculate_best_in_range(7)
    
    def _get_monthly_best(self) -> int:
        """Get best streak this month"""
        return self._calculate_best_in_range(30)
    
    def _calculate_best_in_range(self, days: int) -> int:
        """Calculate best streak in last N days"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        report = self.adherence.calculate_adherence(days=days, end_date=end_date)
        
        best = 0
        current = 0
        
        for day in report.daily_breakdown:
            if day["rate"] >= self.GOOD_DAY_THRESHOLD:
                current += 1
                best = max(best, current)
            else:
                current = 0
        
        return best
    
    def _get_last_good_day(self) -> Optional[date]:
        """Get the last day with good adherence"""
        check_date = date.today()
        
        for _ in range(365):
            report = self.adherence.calculate_adherence(days=1, end_date=check_date)
            
            if report.total_expected > 0 and report.overall_rate >= self.GOOD_DAY_THRESHOLD:
                return check_date
            
            check_date -= timedelta(days=1)
        
        return None
    
    def _is_streak_at_risk(self) -> bool:
        """Check if current streak is at risk of being broken"""
        from datetime import datetime
        
        now = datetime.now()
        
        # If it's late in the day and doses remain
        if now.hour >= self.STREAK_AT_RISK_HOUR:
            today_summary = self.adherence.get_today_summary()
            if not today_summary["complete"] and today_summary["expected"] > 0:
                return True
        
        return False
    
    def _get_milestone_reward(self, milestone: int) -> str:
        """Get reward description for milestone"""
        rewards = {
            7: "Week Warrior Badge 🏅",
            14: "Two Week Triumph 🥈",
            30: "Monthly Master 🥇",
            60: "Double Month Champion 🏆",
            90: "Quarterly Queen/King 👑",
            180: "Half Year Hero 🦸",
            365: "Year Legend 🌟"
        }
        return rewards.get(milestone, f"{milestone} Day Streak!")
    
    def format_streak_info(self, info: StreakInfo) -> Dict:
        """Format streak info for JSON response"""
        return {
            "current_streak": info.current_streak,
            "best_streak": info.best_streak,
            "weekly_best": info.weekly_best,
            "monthly_best": info.monthly_best,
            "last_good_day": info.last_good_day.isoformat() if info.last_good_day else None,
            "streak_at_risk": info.streak_at_risk,
            "milestones": self.get_milestones()
        }
