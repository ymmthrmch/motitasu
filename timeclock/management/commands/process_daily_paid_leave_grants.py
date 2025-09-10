"""
日次有給付与処理コマンド（cron実行用）
"""

from django.core.management.base import BaseCommand
from datetime import date, datetime
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
            1. 本日の日付で全ユーザーの付与処理を実行
            2. 時効消滅処理も同時実行
            3. 処理結果をログ出力
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
            target_date = date.today()
        
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
        users = User.objects.filter(is_active=True)
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
        # 1. 有給付与処理
        self.stdout.write('有給付与処理を実行中...')
        judgments = auto_processor.process_daily_grants(target_date)
        
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
                    user_info = f'ユーザーID不明'  # 実際の実装ではjudgmentにuser情報を含める
                    self.stdout.write(
                        f'  ✓ {user_info}: {judgment.grant_days}日付与 '
                        f'(出勤率: {judgment.attendance_rate:.1%})'
                    )
            
            logger.info(f'有給付与処理完了: 対象{len(judgments)}件, 付与{granted_count}件')
        else:
            self.stdout.write('付与対象ユーザーはいませんでした')
            logger.info('有給付与処理完了: 対象者なし')
        
        # 2. 時効消滅処理
        self.stdout.write('時効消滅処理を実行中...')
        expired_count = self._process_expiration(target_date)
        
        if expired_count > 0:
            self.stdout.write(f'時効消滅処理完了: {expired_count}名のユーザーで時効処理を実行')
            logger.info(f'時効消滅処理完了: {expired_count}名')
        else:
            self.stdout.write('時効消滅対象はありませんでした')
            logger.info('時効消滅処理完了: 対象なし')
        
        self.stdout.write(self.style.SUCCESS('日次有給付与処理が正常に完了しました'))
        logger.info('日次有給付与処理完了')
    
    def _process_expiration(self, target_date):
        """時効消滅処理"""
        from django.contrib.auth import get_user_model
        from timeclock.services.paid_leave_grant_processor import PaidLeaveGrantProcessor
        
        User = get_user_model()
        users = User.objects.filter(is_active=True)
        processed_count = 0
        
        for user in users:
            try:
                processor = PaidLeaveGrantProcessor(user)
                expired_records = processor.process_expiration(target_date)
                
                if expired_records:
                    processed_count += 1
                    total_expired_days = sum(record.days for record in expired_records)
                    self.stdout.write(
                        f'  時効消滅: {user.name} - {total_expired_days}日'
                    )
            
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'ユーザー {user.name} の時効処理でエラー: {e}')
                )
                logger.warning(f'時効処理エラー (ユーザーID: {user.id}): {e}')
                continue
        
        return processed_count