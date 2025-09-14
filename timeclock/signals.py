"""
有給休暇関連シグナル処理

Django Signalsを使用してTimeRecordとPaidLeaveRecordの変更を自動検知し、
必要な処理（再判定・残日数更新）を実行する。

設計方針:
- エラー発生時もシステムが停止しないよう、例外を握りつぶす
- テスト時に無効化できるよう、複数レベルの制御フラグを提供
- ログ出力により処理の可視性を確保
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
import logging
from typing import Optional

from .models import TimeRecord, PaidLeaveRecord

logger = logging.getLogger(__name__)


def _should_skip_signal(func_name: str) -> bool:
    """
    シグナル処理をスキップすべきか判定
    
    Args:
        func_name: チェック対象の関数名
        
    Returns:
        bool: スキップする場合True
    """
    # 設定レベルの無効化フラグをチェック
    if not getattr(settings, 'PAID_LEAVE_SIGNALS_ENABLED', True):
        logger.debug(f"Signal {func_name} skipped: PAID_LEAVE_SIGNALS_ENABLED is False")
        return True
    
    # 関数レベルの無効化フラグをチェック
    func = globals().get(func_name)
    if func and getattr(func, '_disabled', False):
        logger.debug(f"Signal {func_name} skipped: function._disabled is True")
        return True
    
    return False


def _get_auto_processor():
    """
    PaidLeaveAutoProcessorのインスタンスを取得
    遅延インポートによりサーキュラーインポートを回避
    """
    from .services.paid_leave_auto_processor import PaidLeaveAutoProcessor
    return PaidLeaveAutoProcessor()


@receiver(post_save, sender=TimeRecord)
def handle_time_record_save(sender, instance, created, **kwargs):
    """
    TimeRecord保存時の自動再判定
    
    処理内容:
        1. 変更されたレコードの日付と対象ユーザーを特定
        2. PaidLeaveAutoProcessorを使用して再判定処理を実行
        3. シグナル無効化フラグをチェック（テスト時等）
    
    Args:
        sender: シグナル送信元のモデルクラス
        instance: 保存されたTimeRecordインスタンス
        created: 新規作成の場合True
        **kwargs: その他のシグナル引数
    """
    if _should_skip_signal('handle_time_record_save'):
        return
    
    try:
        # 変更されたレコードの日付を取得
        record_date = instance.timestamp.date()
        
        # 変更タイプを判定
        change_type = 'create' if created else 'update'
        
        # デバッグログ
        logger.debug(
            f"TimeRecord {change_type} signal fired: "
            f"user_name={instance.user.name}, date={record_date}, "
            f"clock_type={instance.clock_type}"
        )
        
        # 自動処理を実行
        auto_processor = _get_auto_processor()
        judgments = auto_processor.process_time_record_change(
            instance.user, record_date, change_type
        )
        
        # 処理結果をログ出力
        if judgments:
            logger.info(
                f"TimeRecord {change_type} triggered rejudgment: "
                f"user_name={instance.user.name}, judgment_count={len(judgments)}"
            )
        else:
            logger.debug(
                f"TimeRecord {change_type} did not trigger rejudgment: "
                f"user_name={instance.user.name}"
            )
        
    except Exception as e:
        # エラーログを記録（スタックトレース付き）
        logger.error(
            f"Error in handle_time_record_save: user_name={instance.user.name}, "
            f"error={str(e)}", 
            exc_info=True
        )
        # シグナル処理のエラーは握りつぶして処理を続行


@receiver(post_delete, sender=TimeRecord)
def handle_time_record_delete(sender, instance, **kwargs):
    """
    TimeRecord削除時の自動再判定
    
    処理内容:
        1. 削除されたレコードの日付と対象ユーザーを特定
        2. PaidLeaveAutoProcessorを使用して再判定処理を実行
        3. シグナル無効化フラグをチェック（テスト時等）
    
    Args:
        sender: シグナル送信元のモデルクラス
        instance: 削除されたTimeRecordインスタンス
        **kwargs: その他のシグナル引数
    """
    if _should_skip_signal('handle_time_record_delete'):
        return
    
    try:
        # 削除されたレコードの日付を取得
        record_date = instance.timestamp.date()
        
        # デバッグログ
        logger.debug(
            f"TimeRecord delete signal fired: "
            f"user_name={instance.user.name}, date={record_date}, "
            f"clock_type={instance.clock_type}"
        )
        
        # 自動処理を実行
        auto_processor = _get_auto_processor()
        judgments = auto_processor.process_time_record_change(
            instance.user, record_date, 'delete'
        )
        
        # 処理結果をログ出力
        if judgments:
            logger.info(
                f"TimeRecord deletion triggered rejudgment: "
                f"user_name={instance.user.name}, judgment_count={len(judgments)}"
            )
        else:
            logger.debug(
                f"TimeRecord deletion did not trigger rejudgment: "
                f"user_name={instance.user.name}"
            )
        
    except Exception as e:
        # エラーログを記録（スタックトレース付き）
        logger.error(
            f"Error in handle_time_record_delete: user_name={instance.user.name}, "
            f"error={str(e)}", 
            exc_info=True
        )
        # シグナル処理のエラーは握りつぶして処理を続行


@receiver(post_save, sender=PaidLeaveRecord)
def handle_paid_leave_record_save(sender, instance, created, **kwargs):
    """
    PaidLeaveRecord保存時の残日数更新
    
    処理内容:
        1. 有給使用・付与・取消記録の変更を検知
        2. PaidLeaveAutoProcessorを使用して残日数更新処理を実行
        3. シグナル無効化フラグをチェック（テスト時等）
    
    Args:
        sender: シグナル送信元のモデルクラス
        instance: 保存されたPaidLeaveRecordインスタンス
        created: 新規作成の場合True
        **kwargs: その他のシグナル引数
    """
    if _should_skip_signal('handle_paid_leave_record_save'):
        return
    
    try:
        # 変更タイプを判定
        change_type = 'create' if created else 'update'
        
        # デバッグログ
        logger.debug(
            f"PaidLeaveRecord {change_type} signal fired: "
            f"user_name={instance.user.name}, record_type={instance.record_type}, "
            f"days={instance.days}"
        )
        
        # 自動処理を実行
        auto_processor = _get_auto_processor()
        auto_processor.process_paid_leave_record_change(
            instance.user, instance, change_type
        )
        
        # 処理結果をログ出力
        logger.info(
            f"PaidLeaveRecord {change_type} triggered balance update: "
            f"user_name={instance.user.name}, record_type={instance.record_type}"
        )
        
    except Exception as e:
        # エラーログを記録（スタックトレース付き）
        logger.error(
            f"Error in handle_paid_leave_record_save: user_name={instance.user.name}, "
            f"record_type={instance.record_type}, error={str(e)}", 
            exc_info=True
        )
        # シグナル処理のエラーは握りつぶして処理を続行


@receiver(post_delete, sender=PaidLeaveRecord)
def handle_paid_leave_record_delete(sender, instance, **kwargs):
    """
    PaidLeaveRecord削除時の残日数更新
    
    処理内容:
        1. 有給記録の削除を検知
        2. PaidLeaveAutoProcessorを使用して残日数更新処理を実行
        3. シグナル無効化フラグをチェック（テスト時等）
    
    Args:
        sender: シグナル送信元のモデルクラス
        instance: 削除されたPaidLeaveRecordインスタンス
        **kwargs: その他のシグナル引数
    """
    if _should_skip_signal('handle_paid_leave_record_delete'):
        return
    
    try:
        # デバッグログ
        logger.debug(
            f"PaidLeaveRecord delete signal fired: "
            f"user_name={instance.user.name}, record_type={instance.record_type}, "
            f"days={instance.days}"
        )
        
        # 自動処理を実行
        auto_processor = _get_auto_processor()
        auto_processor.process_paid_leave_record_change(
            instance.user, instance, 'delete'
        )
        
        # 処理結果をログ出力
        logger.info(
            f"PaidLeaveRecord deletion triggered balance update: "
            f"user_name={instance.user.name}, record_type={instance.record_type}"
        )
        
    except Exception as e:
        # エラーログを記録（スタックトレース付き）
        logger.error(
            f"Error in handle_paid_leave_record_delete: user_name={instance.user.name}, "
            f"record_type={instance.record_type}, error={str(e)}", 
            exc_info=True
        )
        # シグナル処理のエラーは握りつぶして処理を続行
