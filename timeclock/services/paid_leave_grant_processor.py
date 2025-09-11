"""
有給休暇付与・取消処理クラス
"""

from datetime import date
from dataclasses import dataclass
from typing import Dict, List, Optional
from django.db.models import Sum, Q
from django.db import transaction

from timeclock.models import PaidLeaveRecord
from .paid_leave_calculator import PaidLeaveJudgment
from .paid_leave_balance_manager import PaidLeaveBalanceManager


class PaidLeaveGrantProcessor:
    """付与・取消の実行処理を担当"""
    
    def __init__(self, user):
        """
        Args:
            user: Userモデルのインスタンス
        """
        self.user = user
        self.balance_manager = PaidLeaveBalanceManager(user)
    
    def _calculate_grant_balance(self, grant_date: date) -> Dict[str, int]:
        """
        特定付与日の残日数情報を効率的に計算
        
        Args:
            grant_date: 付与日
            
        Returns:
            dict: {'used': 使用日数, 'expired': 時効日数, 'cancelled': 取消日数, 'remaining': 残日数}
        """
        # 単一クエリで全ての関連記録を取得
        records = PaidLeaveRecord.objects.filter(
            user=self.user,
            grant_date=grant_date
        ).values('record_type').annotate(total=Sum('days'))
        
        # レコード種別ごとの合計を辞書化
        totals = {record['record_type']: record['total'] for record in records}
        
        used_days = totals.get('use', 0)
        expired_days = totals.get('expire', 0)
        cancelled_days = totals.get('cancel', 0)
        granted_days = totals.get('grant', 0)
        
        remaining_days = max(0, granted_days - used_days - expired_days - cancelled_days)
        
        return {
            'used': used_days,
            'expired': expired_days,
            'cancelled': cancelled_days,
            'granted': granted_days,
            'remaining': remaining_days
        }
    
    @transaction.atomic
    def execute_grant(self, judgment: PaidLeaveJudgment) -> Optional[PaidLeaveRecord]:
        """
        付与処理を実行
        
        Args:
            judgment: 付与判定結果
            
        Returns:
            PaidLeaveRecord: 作成された付与記録（付与不適格の場合はNone）
            
        Rules:
            - 判定結果に基づいてPaidLeaveRecordを作成
            - 残日数の更新も実行
        """
        # 付与不適格または付与日数0の場合は何も作成しない
        if not judgment.is_eligible or judgment.grant_days <= 0:
            return None
        
        # 正常な付与処理
        grant_record = PaidLeaveRecord.objects.create(
            user=self.user,
            record_type='grant',
            days=judgment.grant_days,
            grant_date=judgment.judgment_date,
            expiry_date=judgment.expiry_date,
            description=judgment.description
        )
        
        # 残日数更新
        self.balance_manager.update_user_balance()
        
        return grant_record
    
    def _get_grant_record(self, grant_date: date) -> PaidLeaveRecord:
        """付与記録を取得"""
        try:
            return PaidLeaveRecord.objects.get(
                user=self.user,
                record_type='grant',
                grant_date=grant_date
            )
        except PaidLeaveRecord.DoesNotExist:
            raise ValueError(f"{grant_date}の付与記録が見つかりません")
    
    @transaction.atomic
    def execute_cancellation(self, target_date: date, cancellation_days: int) -> List[PaidLeaveRecord]:
        """
        付与取消処理を実行（部分取消対応）
        
        Args:
            grant_date: 取消対象の付与日
            cancellation_days: 取消日数
            
        Returns:
            PaidLeaveRecord: 編集された付与記録（付与不適格の場合はNone）
            
        Rules:
            - 指定付与日の付与の付与日数を編集することで取消
            - 残日数がマイナスにならない範囲でのみ取消
        """
        target_records = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant',
            grant_date=target_date
        ).order_by('created_at')
        
        if not target_records.exists():
            raise ValueError(f"{target_date}の付与記録が見つかりません")
        
        # 残り取消日数
        remaining_cancellation_days = cancellation_days
        modified_record = None
        
        # 古いものから順に取消処理
        for target_record in target_records:
            if remaining_cancellation_days <= 0:
                break
            
            # この記録から取消可能な日数（0以上を維持）
            reducible_days = min(target_record.days, remaining_cancellation_days)
            
            if reducible_days > 0:
                # 付与日数を減らす
                target_record.days -= reducible_days
                target_record.save()
                
                # 取消日数を減らす
                remaining_cancellation_days -= reducible_days
                
                # 最初に編集された記録を保持
                if modified_record is None:
                    modified_record = target_record
        
        # 残日数を更新
        self.balance_manager.update_user_balance()
        
        return modified_record
    
    def _mark_as_expired(self, grant_record: PaidLeaveRecord) -> PaidLeaveRecord:
        """時効消滅フラグを設定"""
        grant_record.expired = True
        grant_record.save()
        return grant_record
    
    @transaction.atomic
    def process_expiration(self, target_date: date) -> List[PaidLeaveRecord]:
        """
        時効消滅処理を実行
        
        Args:
            target_date: 処理対象日
            
        Returns:
            list[PaidLeaveRecord]: 消滅させた有給記録のリスト
            
        Rules:
            - target_date時点で期限切れの未使用有給を消滅
            - 時効記録をPaidLeaveRecordに作成
        """
        # 期限切れの有給記録を取得（まだ時効になっていないもの）
        expired_grant_records = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant',
            expiry_date__lte=target_date,
            expired=False
        )
        
        expired_list = []
        
        for grant_record in expired_grant_records:
            expired_record = self._mark_as_expired(grant_record)
            expired_list.append(expired_record)

        if expired_list:
            self.balance_manager.update_user_balance()
        
        return expired_list