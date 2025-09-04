from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.db import models
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import logging

from timeclock.models import PaidLeaveRecord
from timeclock.services.paid_leave_service import PaidLeaveService

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '有給休暇の付与・時効処理と整合性チェックを毎日実行'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の処理は行わず、ログ出力のみ実行'
        )
        parser.add_argument(
            '--fix-inconsistencies',
            action='store_true',
            help='整合性の不整合を自動修正'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix_inconsistencies = options['fix_inconsistencies']
        
        today = timezone.now().date()
        self.stdout.write(f"有給休暇処理開始: {today}")
        
        # 雇用開始日が設定されているユーザーのみ対象
        users = User.objects.filter(hire_date__isnull=False)
        
        grant_count = 0
        expire_count = 0
        inconsistency_count = 0
        
        for user in users:
            service = PaidLeaveService(user)
            
            try:
                with transaction.atomic():
                    # 1. 有給付与処理
                    if self._process_grant(user, service, today, dry_run):
                        grant_count += 1
                    
                    # 2. 時効処理
                    expired_days = self._process_expiry(user, today, dry_run)
                    if expired_days > 0:
                        expire_count += 1
                    
                    # 3. 整合性チェック
                    if self._check_consistency(user, service, fix_inconsistencies, dry_run):
                        inconsistency_count += 1
                        
            except Exception as e:
                logger.error(f"ユーザー {user.name} の処理でエラー: {e}")
                self.stderr.write(f"エラー: {user.name} - {e}")
        
        # 結果報告
        self.stdout.write(
            self.style.SUCCESS(
                f"処理完了: 付与{grant_count}件, 時効{expire_count}件, 不整合修正{inconsistency_count}件"
            )
        )
    
    def _process_grant(self, user, service, today, dry_run):
        """有給付与処理"""
        status = service.get_paid_leave_status()
        
        if not status['next_grant']:
            self.stdout.write(f"{user.name}: 次回付与なし (勤続{status.get('service_months', 0)}ヶ月)")
            return False
        
        next_grant = status['next_grant']
        
        # 今日が付与日で、出勤率条件を満たしているか
        if (next_grant['grant_date'] == today and 
            next_grant['attendance_info']['is_eligible']):
            
            if dry_run:
                self.stdout.write(f"[DRY-RUN] {user.name}: {next_grant['grant_days']}日付与予定")
                return True
            
            # 有給を付与（2年後の同日まで有効）
            expiry_date = today + relativedelta(years=2)
            
            PaidLeaveRecord.objects.create(
                user=user,
                record_type='grant',
                days=next_grant['grant_days'],
                grant_date=today,
                expiry_date=expiry_date,
                description=f"勤続{next_grant['service_months']}ヶ月による法定付与"
            )
            
            logger.info(f"有給付与実行: {user.name} - {next_grant['grant_days']}日")
            return True
        
        return False
    
    def _process_expiry(self, user, today, dry_run):
        """時効処理"""
        # 今日時効になる有給を検索
        expiring_records = PaidLeaveRecord.objects.filter(
            user=user,
            record_type='grant',
            expiry_date=today
        )
        
        expired_days = 0
        for record in expiring_records:
            # この付与分のうち使用されていない分を計算
            used_from_this_grant = PaidLeaveRecord.objects.filter(
                user=user,
                record_type='use',
                grant_date=record.grant_date
            ).aggregate(
                total=models.Sum('days')
            )['total'] or 0
            
            unused_days = max(0, record.days - used_from_this_grant)
            
            if unused_days > 0:
                if dry_run:
                    self.stdout.write(f"[DRY-RUN] {user.name}: {unused_days}日時効予定")
                else:
                    PaidLeaveRecord.objects.create(
                        user=user,
                        record_type='expire',
                        days=unused_days,
                        grant_date=record.grant_date,
                        expiry_date=today,
                        description=f"{record.grant_date}付与分の時効消滅"
                    )
                    logger.info(f"有給時効処理: {user.name} - {unused_days}日")
                
                expired_days += unused_days
        
        return expired_days
    
    def _check_consistency(self, user, service, fix_inconsistencies, dry_run):
        """整合性チェックと修正"""
        correct_days = service.recalculate_current_leave()
        current_days = user.current_paid_leave
        
        if current_days != correct_days:
            self.stdout.write(
                self.style.WARNING(
                    f"不整合検出: {user.name} - 現在{current_days}日, 正しくは{correct_days}日"
                )
            )
            
            if fix_inconsistencies and not dry_run:
                user.current_paid_leave = correct_days
                user.save(update_fields=['current_paid_leave'])
                logger.warning(f"有給日数修正: {user.name} {current_days}→{correct_days}")
                return True
        
        return False