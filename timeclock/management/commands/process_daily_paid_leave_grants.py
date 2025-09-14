"""
日次有給付与処理コマンド（cron実行用）
"""

from django.core.management.base import BaseCommand
from datetime import date, datetime
from django.conf import settings
from django.utils import timezone
from zoneinfo import ZoneInfo
import logging

from timeclock.services.paid_leave_auto_processor import PaidLeaveAutoProcessor


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """日次有給付与処理コマンド（cron実行用）"""
    
    help = '指定日の有給休暇付与処理を実行します'
    
    def add_arguments(self, parser):
        """コマンド引数の定義"""
        parser.add_argument(
            '--date',
            type=str,
            help='処理対象日 (YYYY-MM-DD形式、未指定の場合は今日)',
            default=None
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の処理は実行せず、対象者のみを表示',
            default=False
        )
    
    def handle(self, *args, **options):
        """
        実行内容:
            1. 本日の日付で全ユーザーの付与処理（同時に時効消滅処理）を実行
            2. 処理結果をログ出力
        """
        # 処理対象日の決定
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f'無効な日付形式です: {options["date"]} (YYYY-MM-DD形式で指定してください)')
                )
                return
        else:
            # JST基準で今日の日付を取得
            jst = ZoneInfo(settings.TIME_ZONE)
            target_date = timezone.now().astimezone(jst).date()
        
        self.stdout.write(f'日次有給付与処理を開始します (対象日: {target_date})')
        logger.info(f'日次有給付与処理を開始: 対象日={target_date}')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY-RUN モード: 実際の処理は実行されません'))
        
        try:
            # 自動処理プロセッサーを初期化
            auto_processor = PaidLeaveAutoProcessor()
            
            if options['dry_run']:
                # DRY-RUNモード: 対象者のみ表示
                self._dry_run_check(auto_processor, target_date)
            else:
                # 実際の処理を実行
                self._execute_processing(auto_processor, target_date)
            
        except Exception as e:
            error_msg = f'処理中にエラーが発生しました: {e}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
            raise
    
    def _dry_run_check(self, auto_processor, target_date):
        """DRY-RUN: 処理対象者をチェック"""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        users = User.objects.filter(
            is_active=True,
            hire_date__isnull=False
        ).exclude(paid_leave_grant_schedule=[])
        
        target_users = []
        
        for user in users:
            if user.is_grant_date_today(target_date):
                target_users.append(user)
        
        if target_users:
            self.stdout.write(f'付与処理対象ユーザー数: {len(target_users)}')
            for user in target_users:
                self.stdout.write(f'  - {user.name} (ID: {user.id}, 入社日: {user.hire_date})')
        else:
            self.stdout.write('付与処理対象ユーザーはいません')
    
    def _execute_processing(self, auto_processor, target_date):
        """実際の処理を実行"""
        # 有給付与・時効処理
        self.stdout.write('有給付与・時効処理を実行中...')
        judgments = auto_processor.process_daily_grants_and_expirations(target_date)
        
        # 時効処理の結果をログから集計（処理済みのメッセージをパース）
        self._log_expiration_results(target_date)
        
        if judgments:
            self.stdout.write(f'付与処理完了: {len(judgments)}件の判定を実行')
            
            # 処理結果の詳細表示
            granted_count = sum(1 for j in judgments if j.is_eligible and j.grant_days > 0)
            rejected_count = len(judgments) - granted_count
            
            self.stdout.write(f'  付与成功: {granted_count}件')
            self.stdout.write(f'  付与失敗: {rejected_count}件')
            
            # 付与された詳細情報
            for judgment in judgments:
                if judgment.is_eligible and judgment.grant_days > 0:
                    user_info = f'{judgment.user.name} (Email: {judgment.user.email})'
                    self.stdout.write(
                        f'  ✓ {user_info}: {judgment.grant_days}日付与 '
                        f'(出勤率: {judgment.attendance_rate:.1%})'
                    )
            
            logger.info(f'有給付与処理完了: 対象{len(judgments)}件, 付与{granted_count}件')
        else:
            self.stdout.write('付与対象ユーザーはいませんでした')
            logger.info('有給付与処理完了: 対象者なし')
        
        self.stdout.write(self.style.SUCCESS('日次有給付与・時効処理が正常に完了しました'))
        logger.info('日次有給付与・時効処理完了')
    
    def _log_expiration_results(self, target_date):
        """時効処理の結果をログ出力"""
        from timeclock.models import PaidLeaveRecord
        
        # 本日作成された時効記録を取得
        expired_records = PaidLeaveRecord.objects.filter(
            record_type='expire',
            used_date=target_date  # 時効消滅記録の used_date は処理日
        )
        
        if expired_records:
            total_expired_days = sum(record.days for record in expired_records)
            affected_users = expired_records.values_list('user__name', flat=True).distinct()
            
            self.stdout.write(f'時効処理完了: {len(affected_users)}名のユーザーで{total_expired_days}日が時効消滅')
            
            # ユーザー別の時効詳細
            for user_name in affected_users:
                user_expired_records = expired_records.filter(user__name=user_name)
                user_expired_days = sum(record.days for record in user_expired_records)
                grant_dates = [record.grant_date.strftime('%Y-%m-%d') for record in user_expired_records]
                
                self.stdout.write(
                    f'  ⏰ {user_name}: {user_expired_days}日時効消滅 '
                    f'(付与日: {", ".join(grant_dates)})'
                )
            
            logger.info(f'時効処理完了: 対象{len(affected_users)}名, 消滅{total_expired_days}日')
        else:
            self.stdout.write('時効対象の有給はありませんでした')
            logger.info('時効処理完了: 対象なし')
    