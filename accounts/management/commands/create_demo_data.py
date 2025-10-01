from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import logging

from timeclock.models import TimeRecord, MonthlyTarget, PaidLeaveRecord
from leaderboard.models import LeaderboardEntry
from bulletin_board.models import Message, Reaction

User = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Renderデプロイ時に実行するデモデータ作成スクリプト'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存データがある場合でも強制的に実行する'
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        
        # 既存データのチェック
        if User.objects.exists() and not force:
            self.stdout.write(
                self.style.WARNING('ユーザーデータが既に存在します。--forceオプションを使用して強制実行してください。')
            )
            return

        try:
            with transaction.atomic():
                self.create_demo_data()
                self.stdout.write(
                    self.style.SUCCESS('デモデータの作成が完了しました。')
                )
        except Exception as e:
            logger.error(f"デモデータ作成中にエラーが発生しました: {e}")
            self.stdout.write(
                self.style.ERROR(f'デモデータ作成中にエラーが発生しました: {e}')
            )
            raise

    def create_demo_data(self):
        """デモデータを作成"""
        self.stdout.write('デモデータの作成を開始します...')
        
        # 1. ユーザー作成
        users = self.create_users()
        
        # 2. タイムレコード作成
        self.create_time_records(users)
        
        # 3. 有給休暇記録作成
        self.create_paid_leave_records(users)
        
        # 4. 月別目標作成
        self.create_monthly_targets(users)
        
        # 5. 伝言板メッセージとリアクション作成
        self.create_messages_and_reactions(users)

    def create_users(self):
        """ユーザーデータを作成"""
        self.stdout.write('ユーザーデータを作成中...')
        
        users_data = [
            {
                'email': 'tencho@example.com',
                'name': 'もちた店長',
                'is_staff': True,
                'hire_date': date(2023, 4, 1),
                'weekly_work_days': 6,
            },
            {
                'email': 'worker01@example.com',
                'name': '小平邦彦',
                'is_staff': False,
                'hire_date': date(2023, 10, 1),
                'weekly_work_days': 5,
            },
            {
                'email': 'worker02@example.com',
                'name': '広中平祐',
                'is_staff': False,
                'hire_date': date(2024, 4, 1),
                'weekly_work_days': 4,
            },
            {
                'email': 'worker03@example.com',
                'name': '森重文',
                'is_staff': False,
                'hire_date': date(2024, 10, 1),
                'weekly_work_days': 3,
            },
            {
                'email': 'worker04@example.com',
                'name': '山下真由子',
                'is_staff': False,
                'hire_date': date(2025, 4, 1),
                'weekly_work_days': 2,
            },
            {
                'email': 'demo01@example.com',
                'name': 'デモ太郎',
                'is_staff': False,
                'hire_date': date(2024, 4, 1),
                'weekly_work_days': 4,
            },
        ]
        
        users = {}
        for user_data in users_data:
            user = User.objects.create_user(
                email=user_data['email'],
                name=user_data['name'],
                password='motitasu'
            )
            user.is_staff = user_data['is_staff']
            user.hire_date = user_data['hire_date']
            user.weekly_work_days = user_data['weekly_work_days']
            user.save()
            
            users[user_data['email']] = user
            
        return users

    def create_time_records(self, users):
        """タイムレコードを作成"""
        self.stdout.write('タイムレコードを作成中...')
        
        jst = ZoneInfo('Asia/Tokyo')
        today = date.today()
        
        # 店長のタイムレコード（9-18時、13-14時休憩）
        manager = users['tencho@example.com']
        self.create_manager_time_records(manager, jst, today)
        
        # アルバイトのタイムレコード（15-18時）
        worker_emails = ['worker01@example.com', 'worker02@example.com', 'worker03@example.com', 'worker04@example.com', 'demo01@example.com']
        for email in worker_emails:
            worker = users[email]
            self.create_worker_time_records(worker, jst, today)

    def create_manager_time_records(self, manager, jst, today):
        """店長のタイムレコードを作成"""
        current_date = manager.hire_date
        
        while current_date <= today:
            # 週の曜日を取得（0=月曜日）
            weekday = current_date.weekday()
            
            # 店長の週6勤務（日曜日休み、日曜日は6）
            if weekday != 6:  
                # 9時出勤
                clock_in_time = datetime.combine(current_date, datetime.min.time().replace(hour=9))
                clock_in_time = clock_in_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=manager,
                    clock_type='clock_in',
                    timestamp=clock_in_time
                )
                
                # 13時休憩開始
                break_start_time = datetime.combine(current_date, datetime.min.time().replace(hour=13))
                break_start_time = break_start_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=manager,
                    clock_type='break_start',
                    timestamp=break_start_time
                )
                
                # 14時休憩終了
                break_end_time = datetime.combine(current_date, datetime.min.time().replace(hour=14))
                break_end_time = break_end_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=manager,
                    clock_type='break_end',
                    timestamp=break_end_time
                )
                
                # 18時退勤
                clock_out_time = datetime.combine(current_date, datetime.min.time().replace(hour=18))
                clock_out_time = clock_out_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=manager,
                    clock_type='clock_out',
                    timestamp=clock_out_time
                )
                
            current_date += timedelta(days=1)

    def create_worker_time_records(self, worker, jst, today):
        """アルバイトのタイムレコードを作成"""
        current_date = worker.hire_date
        work_days_count = 0
        
        while current_date <= today:
            weekday = current_date.weekday()
            
            # 週の所定労働日数に応じて勤務パターンを決定
            should_work = False
            if worker.weekly_work_days == 5:  # 平日勤務
                should_work = weekday < 5
            elif worker.weekly_work_days == 4:  # 月火木金
                should_work = weekday in [0, 1, 3, 4]
            elif worker.weekly_work_days == 3:  # 月水金
                should_work = weekday in [0, 2, 4]
            elif worker.weekly_work_days == 2:  # 火木
                should_work = weekday in [1, 3]
                
            if should_work:
                # 15時出勤
                clock_in_time = datetime.combine(current_date, datetime.min.time().replace(hour=15))
                clock_in_time = clock_in_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=worker,
                    clock_type='clock_in',
                    timestamp=clock_in_time
                )
                
                # 18時退勤
                clock_out_time = datetime.combine(current_date, datetime.min.time().replace(hour=18))
                clock_out_time = clock_out_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=worker,
                    clock_type='clock_out',
                    timestamp=clock_out_time
                )
                
            current_date += timedelta(days=1)

    def create_paid_leave_records(self, users):
        """有給休暇記録を作成"""
        self.stdout.write('有給休暇記録を作成中...')
        
        from timeclock.services.paid_leave_auto_processor import PaidLeaveAutoProcessor
        
        # 全ユーザーの有給付与処理を実行
        for user in users.values():
            if user.hire_date:
                processor = PaidLeaveAutoProcessor()
                # 入社日から今日までの期間で付与処理を実行
                current_date = user.hire_date
                today = date.today()
                
                while current_date <= today:
                    # 日次付与処理を実行（該当日に付与されるユーザーのみ処理される）
                    processor.process_daily_grants_and_expirations(current_date)
                    current_date += timedelta(days=1)
        
        # デモ用01の有給使用記録を追加
        demo_user = users.get('demo01@example.com')
        if demo_user:
            # 2025/05/01に有給使用
            try:
                grant_record = PaidLeaveRecord.objects.filter(
                    user=demo_user,
                    record_type='grant'
                ).first()
                
                if grant_record:
                    PaidLeaveRecord.objects.create(
                        user=demo_user,
                        record_type='use',
                        days=1,
                        grant_date=grant_record.grant_date,
                        expiry_date=grant_record.expiry_date,
                        used_date=date(2025, 5, 1),
                        description='有給休暇使用'
                    )
                    
                    # 2025/06/01にも有給使用
                    PaidLeaveRecord.objects.create(
                        user=demo_user,
                        record_type='use',
                        days=1,
                        grant_date=grant_record.grant_date,
                        expiry_date=grant_record.expiry_date,
                        used_date=date(2025, 6, 1),
                        description='有給休暇使用'
                    )
                    
                    # 残日数を更新
                    demo_user.current_paid_leave = max(0, demo_user.current_paid_leave - 2)
                    demo_user.save()
            except Exception as e:
                logger.warning(f"デモ用01の有給使用記録作成に失敗: {e}")

    def create_monthly_targets(self, users):
        """月別目標を作成"""
        self.stdout.write('月別目標を作成中...')
        
        demo_user = users.get('demo01@example.com')
        if demo_user:
            # 2025年7月の目標
            MonthlyTarget.objects.create(
                user=demo_user,
                year=2025,
                month=7,
                target_income=100000
            )
            
            # 2025年8月の目標
            MonthlyTarget.objects.create(
                user=demo_user,
                year=2025,
                month=8,
                target_income=100000
            )

    def create_messages_and_reactions(self, users):
        """伝言板メッセージとリアクションを作成"""
        self.stdout.write('伝言板メッセージとリアクションを作成中...')
        
        jst = ZoneInfo('Asia/Tokyo')
        today = timezone.now().astimezone(jst)
        
        # メッセージデータ
        messages_data = [
            {
                'user': 'tencho@example.com',
                'content': '来月のシフト締め切りが今週末です。みなさん忘れないようにー！',
                'show_name': True,
                'days_ago': 2,
                'is_pinned': True,
                'pin_duration_hours': 168,  # 1週間
            },
            {
                'user': 'worker01@example.com',
                'content': '今日純売り上げが20万超えました！忙しかったですね。お疲れ様でした〜',
                'show_name': False,
                'days_ago': 4,
            },
            {
                'user': 'worker02@example.com',
                'content': '明日オープンの方、サンドイッチの仕込み終わらなかったのでおねがします！すみません汗',
                'show_name': False,
                'days_ago': 6,
            },
            {
                'user': 'worker03@example.com',
                'content': '風邪治りました！シフト変わってくださった方ありがとうございました！',
                'show_name': True,
                'days_ago': 8,
            },
            {
                'user': 'worker04@example.com',
                'content': '駅前のパン屋さんの新商品美味しかったです！おすすめ♪',
                'show_name': False,
                'days_ago': 10,
            },
            {
                'user': 'demo01@example.com',
                'content': '来週から新メニューですね。楽しみです！',
                'show_name': True,
                'days_ago': 12,
            },
            {
                'user': 'tencho@example.com',
                'content': 'エアコンの調子が悪いので業者に連絡しました。明日修理予定です。',
                'show_name': True,
                'days_ago': 14,
            },
            {
                'user': 'worker01@example.com',
                'content': '今日のお客様、常連の○○さんがケーキを褒めてくださいました！嬉しい〜',
                'show_name': False,
                'days_ago': 16,
            },
        ]
        
        messages = []
        for msg_data in messages_data:
            user = users[msg_data['user']]
            created_at = today - timedelta(days=msg_data['days_ago'])
            
            message = Message.objects.create(
                user=user,
                content=msg_data['content'],
                show_name=msg_data['show_name'],
                created_at=created_at
            )
            
            # ピン留めメッセージの設定
            if msg_data.get('is_pinned'):
                message.pin_message(msg_data['pin_duration_hours'])
                
            messages.append(message)
        
        # リアクションデータ
        reactions_data = [
            # メッセージ1（シフト締切）：アルバイト1,2,3が👍
            {'message_idx': 0, 'users': ['worker01@example.com', 'worker02@example.com', 'worker03@example.com'], 'reaction': 'thumbs_up'},
            # メッセージ2（売上20万）：店長が👍、アルバイト2,3が😮、デモ用01が❤️
            {'message_idx': 1, 'users': ['tencho@example.com'], 'reaction': 'thumbs_up'},
            {'message_idx': 1, 'users': ['worker02@example.com', 'worker03@example.com'], 'reaction': 'surprised'},
            {'message_idx': 1, 'users': ['demo01@example.com'], 'reaction': 'heart'},
            # メッセージ3（仕込み依頼）：アルバイト1が👍、店長が👍
            {'message_idx': 2, 'users': ['worker01@example.com', 'tencho@example.com'], 'reaction': 'thumbs_up'},
            # メッセージ4（風邪回復）：店長が❤️、アルバイト1,2が👍、デモ用01が😂
            {'message_idx': 3, 'users': ['tencho@example.com'], 'reaction': 'heart'},
            {'message_idx': 3, 'users': ['worker01@example.com', 'worker02@example.com'], 'reaction': 'thumbs_up'},
            {'message_idx': 3, 'users': ['demo01@example.com'], 'reaction': 'laughing'},
            # メッセージ5（パン屋情報）：アルバイト1,3が❤️、デモ用01が👍
            {'message_idx': 4, 'users': ['worker01@example.com', 'worker03@example.com'], 'reaction': 'heart'},
            {'message_idx': 4, 'users': ['demo01@example.com'], 'reaction': 'thumbs_up'},
            # メッセージ6（新メニュー）：店長が👍、アルバイト2が❤️
            {'message_idx': 5, 'users': ['tencho@example.com'], 'reaction': 'thumbs_up'},
            {'message_idx': 5, 'users': ['worker02@example.com'], 'reaction': 'heart'},
            # メッセージ7（エアコン修理）：全員が👍
            {'message_idx': 6, 'users': list(users.keys()), 'reaction': 'thumbs_up'},
            # メッセージ8（お客様の声）：店長が❤️、アルバイト2,3,4が👍、デモ用01が😂
            {'message_idx': 7, 'users': ['tencho@example.com'], 'reaction': 'heart'},
            {'message_idx': 7, 'users': ['worker02@example.com', 'worker03@example.com', 'worker04@example.com'], 'reaction': 'thumbs_up'},
            {'message_idx': 7, 'users': ['demo01@example.com'], 'reaction': 'laughing'},
        ]
        
        for reaction_data in reactions_data:
            message = messages[reaction_data['message_idx']]
            for user_email in reaction_data['users']:
                user = users[user_email]
                try:
                    Reaction.objects.create(
                        user=user,
                        message=message,
                        reaction_type=reaction_data['reaction']
                    )
                except Exception as e:
                    # 重複などのエラーは無視
                    pass