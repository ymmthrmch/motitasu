from datetime import datetime, timedelta, date
from typing import Dict, Optional, Any
from django.utils import timezone
from zoneinfo import ZoneInfo

from ..models import TimeRecord, MonthlyTarget


class WorkTimeService:
    """労働時間・給与計算サービス"""
    
    def __init__(self, user):
        self.user = user
        self.jst = ZoneInfo('Asia/Tokyo')
    
    def get_daily_summary(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        指定日の労働時間と給与を計算する
        
        Args:
            target_date: 計算対象日（Noneの場合は本日）
            
        Returns:
            {
                'date': date,
                'work_time': timedelta,
                'break_time': timedelta,
                'work_hours': float,
                'break_hours': float,
                'wage': int,
                'has_clock_out': bool,
                'error': str or None
            }
        """
        if target_date is None:
            target_date = timezone.now().astimezone(self.jst).date()
        
        # 日付の開始と終了時刻を設定
        day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=self.jst)
        day_end = day_start + timedelta(days=1)
        
        # 指定日の打刻記録を取得
        records = TimeRecord.objects.filter(
            user=self.user,
            timestamp__gte=day_start,
            timestamp__lt=day_end
        ).order_by('timestamp')
        
        if not records.exists():
            return {
                'date': target_date,
                'work_time': timedelta(0),
                'break_time': timedelta(0),
                'work_hours': 0.0,
                'break_hours': 0.0,
                'wage': 0,
                'has_clock_out': False,
                'error': '打刻記録がありません'
            }
        
        # 労働時間と休憩時間を計算
        result = self._calculate_work_and_break_time(records)
        
        # 時給から給与を計算
        hourly_wage = self.user.hourly_wage if hasattr(self.user, 'hourly_wage') else None
        work_hours = result['work_time'].total_seconds() / 3600
        wage = int(work_hours * hourly_wage) if hourly_wage else 0
        
        return {
            'date': target_date,
            'work_time': result['work_time'],
            'break_time': result['break_time'],
            'work_hours': round(work_hours, 2),
            'break_hours': round(result['break_time'].total_seconds() / 3600, 2),
            'wage': wage,
            'has_clock_out': result['has_clock_out'],
            'error': None
        }
    
    def get_monthly_summary(self, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        """
        月次の労働時間と給与を計算する
        
        Args:
            year: 年（Noneの場合は今年）
            month: 月（Noneの場合は今月）
            
        Returns:
            月次サマリー情報
        """
        now_jst = timezone.now().astimezone(self.jst)
        if year is None:
            year = now_jst.year
        if month is None:
            month = now_jst.month
        
        # 月初から月末（または今日）までの日付リスト
        start_date = date(year, month, 1)
        today = now_jst.date()
        
        # 月末日を計算
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # 集計終了日は今日か月末のどちらか早い方
        end_date = min(end_date, today)
        
        # 日ごとのサマリーを取得
        daily_summaries = []
        total_work_time = timedelta(0)
        total_break_time = timedelta(0)
        total_wage = 0
        work_days = 0
        
        current_date = start_date
        while current_date <= end_date:
            daily = self.get_daily_summary(current_date)
            if daily['work_hours'] > 0:
                daily_summaries.append(daily)
                total_work_time += daily['work_time']
                total_break_time += daily['break_time']
                total_wage += daily['wage']
                work_days += 1
            current_date += timedelta(days=1)
        
        # 目標月収に対する達成率を計算
        try:
            target_obj = MonthlyTarget.objects.get(user=self.user, year=year, month=month)
            target_income = target_obj.target_income
        except MonthlyTarget.DoesNotExist:
            target_income = None
        
        achievement_rate = None
        if target_income and target_income > 0:
            achievement_rate = round((total_wage / target_income) * 100, 1)
        
        return {
            'year': year,
            'month': month,
            'work_days': work_days,
            'total_work_time': total_work_time,
            'total_break_time': total_break_time,
            'total_work_hours': round(total_work_time.total_seconds() / 3600, 2),
            'total_break_hours': round(total_break_time.total_seconds() / 3600, 2),
            'total_wage': total_wage,
            'target_income': target_income,
            'achievement_rate': achievement_rate,
            'daily_summaries': daily_summaries
        }
    
    def _calculate_work_and_break_time(self, records) -> Dict[str, Any]:
        """
        打刻記録から労働時間と休憩時間を計算する
        
        Args:
            records: 打刻記録のクエリセット
            
        Returns:
            労働時間と休憩時間の辞書
        """
        work_time = timedelta(0)
        break_time = timedelta(0)
        clock_in_time = None
        break_start_time = None
        has_clock_out = False
        
        for record in records:
            if record.clock_type == 'clock_in':
                clock_in_time = record.timestamp
                
            elif record.clock_type == 'break_start':
                if clock_in_time:
                    # 出勤から休憩開始までの時間を労働時間に追加
                    work_time += record.timestamp - clock_in_time
                    clock_in_time = None
                break_start_time = record.timestamp
                
            elif record.clock_type == 'break_end':
                if break_start_time:
                    # 休憩時間を計算
                    break_time += record.timestamp - break_start_time
                    break_start_time = None
                    # 休憩終了後は勤務再開とみなす
                    clock_in_time = record.timestamp
                    
            elif record.clock_type == 'clock_out':
                if clock_in_time:
                    # 最後の勤務時間を追加
                    work_time += record.timestamp - clock_in_time
                    clock_in_time = None
                has_clock_out = True
                break  # 退勤したら計算終了
        
        # 退勤していない場合の処理（現在時刻までを計算）
        if clock_in_time and not has_clock_out:
            current_time = timezone.now().astimezone(self.jst)
            work_time += current_time - clock_in_time
        elif break_start_time and not has_clock_out:
            current_time = timezone.now().astimezone(self.jst)
            break_time += current_time - break_start_time
        
        return {
            'work_time': work_time,
            'break_time': break_time,
            'has_clock_out': has_clock_out
        }
    
    def format_timedelta(self, td: timedelta) -> str:
        """
        timedeltaを時分形式の文字列に変換
        
        Args:
            td: timedelta オブジェクト
            
        Returns:
            "X時間Y分" 形式の文字列
        """
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}時間{minutes}分"
        else:
            return f"{minutes}分"