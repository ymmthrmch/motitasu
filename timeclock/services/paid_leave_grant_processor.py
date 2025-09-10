"""
有給休暇付与・取消処理クラス
"""

from datetime import date
from dataclasses import dataclass
from typing import List
from django.db.models import Sum

from timeclock.models import PaidLeaveRecord
from .paid_leave_calculator import PaidLeaveJudgment
from .paid_leave_balance_manager import PaidLeaveBalanceManager


@dataclass
class CancellationResult:
    """取消処理結果"""
    grant_count: int            # 取消対象の付与回数
    target_cancel_days: int     # 当初の取消予定日数
    actual_cancelled_days: int  # 実際に取り消された日数
    remaining_balance: int      # 取消後の残日数
    was_partial: bool          # 部分取消だったか
    cancellation_date: date    # 取消日
    reason: str                # 取消理由


class PaidLeaveGrantProcessor:
    """付与・取消の実行処理を担当"""
    
    def __init__(self, user):
        """
        Args:
            user: Userモデルのインスタンス
        """
        self.user = user
        self.balance_manager = PaidLeaveBalanceManager(user)
    
    def execute_grant(self, judgment: PaidLeaveJudgment) -> PaidLeaveRecord:
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
        if not judgment.is_eligible or judgment.grant_days <= 0:
            # 付与不適格または付与日数0の場合は何も作成しない
            return None
        
        # 正常な付与処理
        grant_record = PaidLeaveRecord.objects.create(
            user=self.user,
            record_type='grant',
            days=judgment.grant_days,
            grant_date=judgment.judgment_date,
            expiry_date=judgment.expiry_date,
            reason=judgment.reason
        )
        
        # grant_count情報を追加（テスト検証用）
        grant_record.grant_count = judgment.grant_count
        
        # 残日数更新
        self.balance_manager.update_user_balance()
        
        return grant_record
    
    def execute_cancellation(self, grant_count: int, cancellation_date: date, reason: str) -> CancellationResult:
        """
        付与取消処理を実行（部分取消対応）
        
        Args:
            grant_count: 取消対象の付与回数
            cancellation_date: 取消日
            reason: 取消理由
            
        Returns:
            CancellationResult: 取消処理結果
            
        Rules:
            - 指定回の付与を部分取消で処理
            - 残日数がマイナスにならない範囲でのみ取消
            - 取消記録をPaidLeaveRecordに作成
        """
        # 対象の付与記録を取得（grant_countフィールドがないため、順序で特定）
        grant_records = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant'
        ).order_by('grant_date')
        
        # grant_count番目の記録を取得（1-indexedなのでgrant_count-1）
        if grant_records.count() < grant_count:
            raise ValueError(f"{grant_count}回目の付与記録が見つかりません")
        
        grant_record = list(grant_records)[grant_count - 1]  # 0-indexedに変換
        target_grant_date = grant_record.grant_date
        target_cancel_days = grant_record.days
        
        # 現在のこの付与分の残日数を計算
        used_days = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='use',
            grant_date=target_grant_date
        ).aggregate(total=Sum('days'))['total'] or 0
        
        expired_days = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='expire',
            grant_date=target_grant_date
        ).aggregate(total=Sum('days'))['total'] or 0
        
        already_cancelled_days = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='cancel',
            grant_date=target_grant_date
        ).aggregate(total=Sum('days'))['total'] or 0
        
        current_balance_for_this_grant = grant_record.days - used_days - expired_days - already_cancelled_days
        current_balance_for_this_grant = max(0, current_balance_for_this_grant)
        
        # 部分取消計算
        actual_cancelled_days = min(target_cancel_days, current_balance_for_this_grant)
        remaining_balance_for_grant = current_balance_for_this_grant - actual_cancelled_days
        
        # 取消記録を作成
        if actual_cancelled_days > 0:
            cancel_record = PaidLeaveRecord.objects.create(
                user=self.user,
                record_type='cancel',
                days=actual_cancelled_days,
                grant_date=target_grant_date,
                expiry_date=grant_record.expiry_date,
                cancellation_date=cancellation_date,
                reason=reason
            )
            # grant_count情報を追加（テスト検証用）
            cancel_record.grant_count = grant_count
        
        # 全体の残日数を更新
        total_remaining_balance = self.balance_manager.update_user_balance()
        
        # 結果を返す
        was_partial = actual_cancelled_days < target_cancel_days
        
        return CancellationResult(
            grant_count=grant_count,
            target_cancel_days=target_cancel_days,
            actual_cancelled_days=actual_cancelled_days,
            remaining_balance=total_remaining_balance,
            was_partial=was_partial,
            cancellation_date=cancellation_date,
            reason=reason
        )
    
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
        # 期限切れの有給記録を取得
        expired_grant_records = PaidLeaveRecord.objects.filter(
            user=self.user,
            record_type='grant',
            expiry_date__lte=target_date
        )
        
        expired_list = []
        
        # grant_recordsを順序付きリストに変換してindexを取得
        grant_records_list = list(expired_grant_records.order_by('grant_date'))
        
        for i, grant_record in enumerate(grant_records_list):
            # この付与日の使用済み日数を計算
            used_days = PaidLeaveRecord.objects.filter(
                user=self.user,
                record_type='use',
                grant_date=grant_record.grant_date
            ).aggregate(total=Sum('days'))['total'] or 0
            
            # この付与日の既に時効になった日数を計算
            already_expired_days = PaidLeaveRecord.objects.filter(
                user=self.user,
                record_type='expire',
                grant_date=grant_record.grant_date
            ).aggregate(total=Sum('days'))['total'] or 0
            
            # この付与日の取消済み日数を計算
            cancelled_days = PaidLeaveRecord.objects.filter(
                user=self.user,
                record_type='cancel',
                grant_date=grant_record.grant_date
            ).aggregate(total=Sum('days'))['total'] or 0
            
            # 未使用日数を計算
            unused_days = grant_record.days - used_days - already_expired_days - cancelled_days
            
            if unused_days > 0:
                # 時効消滅記録を作成
                expire_record = PaidLeaveRecord.objects.create(
                    user=self.user,
                    record_type='expire',
                    days=unused_days,
                    grant_date=grant_record.grant_date,
                    expiry_date=grant_record.expiry_date,
                    reason="有効期限による時効消滅"
                )
                
                # grant_count情報を追加（テスト検証用）
                expire_record.grant_count = i + 1  # 1-indexed
                expired_list.append(expire_record)
        
        # 残日数を更新
        if expired_list:
            self.balance_manager.update_user_balance()
        
        return expired_list