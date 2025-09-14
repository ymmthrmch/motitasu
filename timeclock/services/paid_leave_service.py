from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional
from django.utils import timezone
from django.conf import settings
from zoneinfo import ZoneInfo
from django.db.models import Sum, Q
from dateutil.relativedelta import relativedelta

from ..models import TimeRecord, PaidLeaveRecord


class PaidLeaveService:
    """有給休暇計算サービス"""
    
    # 通常労働者の付与日数テーブル（勤続月数ベース）
    FULL_TIME_GRANT_TABLE = {
        6: 10, 18: 11, 30: 12, 42: 14, 
        54: 16, 66: 18, 78: 20
    }
    
    # 短時間労働者の付与日数テーブル（週労働日数: {勤続月数: 付与日数}）
    PART_TIME_GRANT_TABLE = {
        4: {6: 7, 18: 8, 30: 9, 42: 10, 54: 12, 66: 13, 78: 15},
        3: {6: 5, 18: 6, 30: 6, 42: 8, 54: 9, 66: 10, 78: 11},
        2: {6: 3, 18: 4, 30: 4, 42: 5, 54: 6, 66: 6, 78: 7},
        1: {6: 1, 18: 2, 30: 2, 42: 2, 54: 3, 66: 3, 78: 3},
    }
    
    def __init__(self, user):
        self.user = user
        self.jst = ZoneInfo(settings.TIME_ZONE)
    
    def get_paid_leave_status(self) -> Dict[str, Any]:
        """現在の有給休暇状況を取得"""
        if not self.user.hire_date:
            return {
                'current_days': 0,
                'next_grant': None,
                'error': '雇用開始日が設定されていません'
            }
        
        try:
            today = timezone.now().astimezone(self.jst).date()
            hire_date = self.user.hire_date
            
            # 勤続月数を計算
            service_months = self._calculate_service_months(hire_date, today)
            
            # 次回付与情報を計算
            next_grant_info = self._calculate_next_grant(hire_date, today, service_months)
            
            # 現在の有給休暇残日数
            current_days = self.user.current_paid_leave
            
            return {
                'current_days': current_days,
                'service_months': service_months,
                'next_grant': next_grant_info,
                'error': None
            }
        except Exception as e:
            return {
                'current_days': 0,
                'next_grant': None,
                'error': f'エラー: {str(e)}'
            }
    
    def _calculate_service_months(self, hire_date: date, current_date: date) -> int:
        """勤続月数を計算"""
        if hire_date > current_date:
            return 0  # 未来の雇用開始日の場合は0ヶ月
        delta = relativedelta(current_date, hire_date)
        return delta.years * 12 + delta.months
    
    def _calculate_next_grant(self, hire_date: date, current_date: date, service_months: int) -> Optional[Dict[str, Any]]:
        """次回有給休暇付与情報を計算"""
        # 未来の雇用開始日の場合は付与なし
        if hire_date > current_date:
            return None
            
        next_milestone = self._find_next_grant_milestone(hire_date, service_months)
        
        if next_milestone is None:
            return None
        
        # 次回付与日を計算
        next_grant_date = hire_date + relativedelta(months=next_milestone)
        
        # 付与日が過去すぎる場合は除外（1日前まではOK）
        if next_grant_date < current_date - timedelta(days=1):
            return None
        
        # 次回付与される日数
        next_grant_days = self._get_grant_days_by_months(next_milestone)
        
        # 出勤率チェック用の情報を計算
        attendance_info = self._calculate_required_attendance(hire_date, next_grant_date, current_date, next_milestone)
        
        return {
            'grant_date': next_grant_date,
            'grant_days': next_grant_days,
            'service_months': next_milestone,
            'days_until_grant': (next_grant_date - current_date).days,
            'attendance_info': attendance_info
        }
    
    def _find_next_grant_milestone(self, hire_date: date, service_months: int) -> Optional[int]:
        """次の付与マイルストーンを見つける"""
        grant_milestones = [6, 18, 30, 42, 54, 66, 78]
        
        # 78ヶ月以降は年次付与ロジックを優先
        if service_months >= 78:
            annual_milestone = self._find_annual_grant_milestone(hire_date, service_months)
            if annual_milestone:
                return annual_milestone
        
        # 基本マイルストーンを逆順で確認
        achieved_milestones = [m for m in reversed(grant_milestones) if service_months >= m]
        
        for milestone in achieved_milestones:
            grant_date = hire_date + relativedelta(months=milestone)
            if not self._is_already_granted(grant_date):
                return milestone
        
        # 将来のマイルストーンを確認
        future_milestones = [m for m in grant_milestones if service_months < m]
        if future_milestones:
            return future_milestones[0]
        
        return None
    
    def _is_already_granted(self, grant_date: date) -> bool:
        """指定日に既に付与済みかチェック"""
        return PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant',
            grant_date=grant_date
        ).exists()
    
    def _find_annual_grant_milestone(self, hire_date: date, service_months: int) -> Optional[int]:
        """78ヶ月以降の年次付与マイルストーンを見つける"""
        # 78ヶ月以降は毎年（12ヶ月ごと）付与: 78, 90, 102, 114, 126...
        # 最新のマイルストーンから逆順でチェック
        max_milestone = ((service_months - 78) // 12) * 12 + 78
        
        current_milestone = max_milestone
        while current_milestone >= 78:
            if service_months >= current_milestone:
                grant_date = hire_date + relativedelta(months=current_milestone)
                if not self._is_already_granted(grant_date):
                    return current_milestone
            current_milestone -= 12
        return None
    
    def _get_grant_days_by_months(self, service_months: int) -> int:
        """勤続月数に応じた付与日数を取得"""
        weekly_work_days = self.user.weekly_work_days
        
        if weekly_work_days >= 5:
            # 通常労働者
            if service_months >= 78:
                return 20  # 6年6か月以降は常に20日
            return self.FULL_TIME_GRANT_TABLE.get(service_months, 0)
        else:
            # 短時間労働者
            table = self.PART_TIME_GRANT_TABLE.get(weekly_work_days, {})
            if service_months >= 78:
                # 6年6か月以降の日数を取得
                return table.get(78, 0)
            return table.get(service_months, 0)
    
    def _calculate_required_attendance(self, hire_date: date, next_grant_date: date, current_date: date, next_milestone: int) -> Dict[str, Any]:
        """必要出勤率の計算"""
        # 基準期間を計算
        if next_milestone == 6:
            # 初回付与（雇用開始から6か月間）
            start_date = hire_date
        else:
            # 継続付与（前回付与から1年間）
            start_date = next_grant_date - relativedelta(months=12)
        
        end_date = min(next_grant_date, current_date)
        
        # 基準期間の所定労働日数（概算）
        period_days = (end_date - start_date).days
        weekly_work_days = self.user.weekly_work_days
        required_work_days = int((period_days / 7) * weekly_work_days)
        
        # 実際の出勤日数を計算
        actual_work_days = TimeRecord.objects.filter(
            user=self.user,
            clock_type='clock_in',
            timestamp__date__gte=start_date,
            timestamp__date__lt=end_date
        ).count()
        
        # 必要出勤日数（8割）
        required_attendance = int(required_work_days * 0.8)
        remaining_days = max(0, required_attendance - actual_work_days)
        
        return {
            'period_start': start_date,
            'period_end': end_date,
            'total_required_days': required_work_days,
            'actual_work_days': actual_work_days,
            'required_attendance': required_attendance,
            'remaining_work_days': remaining_days,
            'attendance_rate': round((actual_work_days / required_work_days * 100), 1) if required_work_days > 0 else 0,
            'is_eligible': remaining_days == 0
        }
    
    def recalculate_current_leave(self) -> int:
        """PaidLeaveRecordから現在有効な有給残数を再計算"""
        from django.db.models import Sum
        today = timezone.now().date()
        
        # 有効な付与分の合計
        granted = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant',
            expiry_date__gte=today
        ).aggregate(Sum('days'))['days__sum'] or 0
        
        # 使用済み分の合計
        used = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='use'
        ).aggregate(Sum('days'))['days__sum'] or 0
        
        # 時効消滅分の合計
        expired = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='expire'
        ).aggregate(Sum('days'))['days__sum'] or 0
        
        return max(0, granted - used - expired)