from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, time, timedelta
from timeclock.models import TimeRecord  # 実際のモデル名に変更

User = get_user_model()

class Command(BaseCommand):
    help = '指定ユーザーの出勤記録を作成（既存レコードはスキップ）'

    def add_arguments(self, parser):
        parser.add_argument(
            'identifier',
            type=str,
            help='対象ユーザーの email または name'
        )
        parser.add_argument('--weekly_work_days', type=int, default=5, help='週の労働日数 (デフォルト: 5)')
        parser.add_argument('--start', type=str, required=True, help='開始日 (YYYY-MM-DD)')
        parser.add_argument('--end', type=str, required=True, help='終了日 (YYYY-MM-DD)')

    def handle(self, *args, **options):
        identifier = options['identifier']
        weekly_work_days = options['weekly_work_days']
        start_str = options['start']
        end_str = options['end']

        # ユーザー検索
        users = User.objects.filter(email=identifier) | User.objects.filter(name=identifier)
        count = users.count()

        if count == 0:
            self.stderr.write(self.style.ERROR(f'ユーザー "{identifier}" が存在しません'))
            return
        elif count > 1:
            self.stderr.write(self.style.ERROR(f'ユーザー名 "{identifier}" は複数存在します ({count} 人)'))
            return

        user = users.first()

        # 日付変換
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'日付の形式が不正です: {e}'))
            return

        work_days_count = 0
        skipped_days_count = 0
        current = start_date

        while current <= end_date:
            weekday = current.weekday()  # 0=月, 6=日
            if weekday < weekly_work_days:
                # 既存の出勤/退勤レコードがあるかチェック
                existing_in = TimeRecord.objects.filter(
                    user=user,
                    clock_type='clock_in',
                    timestamp__date=current
                ).exists()
                existing_out = TimeRecord.objects.filter(
                    user=user,
                    clock_type='clock_out',
                    timestamp__date=current
                ).exists()

                if existing_in or existing_out:
                    skipped_days_count += 1
                else:
                    # 新規作成
                    TimeRecord.objects.create(
                        user=user,
                        clock_type='clock_in',
                        timestamp=timezone.make_aware(datetime.combine(current, time(9, 0)))
                    )
                    TimeRecord.objects.create(
                        user=user,
                        clock_type='clock_out',
                        timestamp=timezone.make_aware(datetime.combine(current, time(18, 0)))
                    )
                    work_days_count += 1

            current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f'{user.name} の出勤記録を {work_days_count} 日分作成しました '
            f'（スキップ: {skipped_days_count} 日、期間: {start_date}〜{end_date}）'
        ))
