"""
有給休暇関連シグナル処理
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from datetime import date

from .models import TimeRecord, PaidLeaveRecord


@receiver(post_save, sender=TimeRecord)
@receiver(post_delete, sender=TimeRecord)
def handle_time_record_change(sender, instance, **kwargs):
    """
    TimeRecord変更時の自動再判定
    
    処理内容:
        1. 変更されたレコードの日付と対象ユーザーを特定
        2. PaidLeaveAutoProcessorを使用して再判定処理を実行
        3. シグナル無効化フラグをチェック（テスト時等）
    """
    try:
        # シグナル無効化フラグをチェック（テスト時等で使用）
        if getattr(handle_time_record_change, '_disabled', False):
            return
        
        from .services.paid_leave_auto_processor import PaidLeaveAutoProcessor
        
        # 変更されたレコードの日付を取得
        record_date = instance.timestamp.date()
        
        # 変更タイプを判定
        if kwargs.get('created', False):
            change_type = 'create'
        elif sender == TimeRecord and 'delete' in str(kwargs):
            change_type = 'delete'
        else:
            change_type = 'update'
        
        # 自動処理を実行
        auto_processor = PaidLeaveAutoProcessor()
        auto_processor.process_time_record_change(instance.user, record_date, change_type)
        
    except Exception as e:
        # エラーログを記録（実際の運用時はログフレームワークを使用）
        print(f"TimeRecord変更シグナルでエラー: {e}")


@receiver(post_save, sender=PaidLeaveRecord)
@receiver(post_delete, sender=PaidLeaveRecord)
def handle_paid_leave_record_change(sender, instance, **kwargs):
    """
    PaidLeaveRecord変更時の残日数更新
    
    処理内容:
        1. 有給使用・付与・取消記録の変更を検知
        2. PaidLeaveAutoProcessorを使用して残日数更新処理を実行
        3. シグナル無効化フラグをチェック（テスト時等）
    """
    try:
        # シグナル無効化フラグをチェック（テスト時等で使用）
        if getattr(handle_paid_leave_record_change, '_disabled', False):
            return
        
        from .services.paid_leave_auto_processor import PaidLeaveAutoProcessor
        
        # 変更タイプを判定
        if kwargs.get('created', False):
            change_type = 'create'
        elif sender == PaidLeaveRecord and 'delete' in str(kwargs):
            change_type = 'delete'
        else:
            change_type = 'update'
        
        # 自動処理を実行
        auto_processor = PaidLeaveAutoProcessor()
        auto_processor.process_paid_leave_record_change(instance.user, instance, change_type)
        
    except Exception as e:
        # エラーログを記録（実際の運用時はログフレームワークを使用）
        print(f"PaidLeaveRecord変更シグナルでエラー: {e}")