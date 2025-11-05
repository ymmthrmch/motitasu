from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import logging

from timeclock.models import TimeRecord, MonthlyTarget, PaidLeaveRecord
from leaderboard.models import LeaderboardEntry
from bulletin_board.models import Message, Reaction
from salary.models import (
    Skill,
    SalaryGrade,
    UserSkill,
    SkillApplication,
    UserSalaryGrade,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Renderデプロイ時に実行するデモデータ作成スクリプト"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="既存データがある場合でも強制的に実行する",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)

        # 既存データのチェック
        if User.objects.exists() and not force:
            self.stdout.write(
                self.style.WARNING(
                    "ユーザーデータが既に存在します。--forceオプションを使用して強制実行してください。"
                )
            )
            return

        try:
            with transaction.atomic():
                self.create_demo_data()
                self.stdout.write(
                    self.style.SUCCESS("デモデータの作成が完了しました。")
                )
        except Exception as e:
            logger.error(f"デモデータ作成中にエラーが発生しました: {e}")
            self.stdout.write(
                self.style.ERROR(f"デモデータ作成中にエラーが発生しました: {e}")
            )
            raise

    def create_demo_data(self):
        """デモデータを作成"""
        self.stdout.write("デモデータの作成を開始します...")

        # 既存のデモデータを削除
        self.stdout.write("既存のデモデータを削除中...")
        TimeRecord.objects.all().delete()
        PaidLeaveRecord.objects.all().delete()
        MonthlyTarget.objects.all().delete()
        LeaderboardEntry.objects.all().delete()
        Message.objects.all().delete()
        Reaction.objects.all().delete()
        UserSalaryGrade.objects.all().delete()
        SkillApplication.objects.all().delete()
        UserSkill.objects.all().delete()
        SalaryGrade.objects.all().delete()
        Skill.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("✓ 既存のデモデータの削除が完了しました"))

        # 1. ユーザー作成
        users = self.create_users()

        # 有給休暇シグナルを一時的に無効化（重複付与を防ぐ）
        settings.PAID_LEAVE_SIGNALS_ENABLED = False
        self.stdout.write("有給休暇シグナルを無効化しました")

        # 2. タイムレコード作成
        self.create_time_records(users)

        # 3. 有給休暇記録作成
        self.create_paid_leave_records(users)

        # 有給休暇シグナルを再度有効化
        settings.PAID_LEAVE_SIGNALS_ENABLED = True
        self.stdout.write("有給休暇シグナルを再度有効化しました")

        # 4. 月別目標作成
        self.create_monthly_targets(users)

        # 5. 伝言板メッセージとリアクション作成
        self.create_messages_and_reactions(users)

        # 6. リーダーボードエントリ作成
        self.create_leaderboard_entries(users)

        # 7. 給与グレード・スキルデータ作成
        self.create_salary_data(users)

    def create_users(self):
        """ユーザーデータを作成"""
        self.stdout.write("ユーザーデータを作成中...")

        users_data = [
            {
                "email": "owner01@example.com",
                "name": "音無響子",
                "is_staff": True,
                "hire_date": date(2023, 4, 1),
                "weekly_work_days": 6,
            },
            {
                "email": "worker01@example.com",
                "name": "一の瀬花枝",
                "is_staff": False,
                "hire_date": date(2025, 9, 1),
                "weekly_work_days": 5,
            },
            {
                "email": "worker02@example.com",
                "name": "二階堂望",
                "is_staff": False,
                "hire_date": date(2023, 10, 1),
                "weekly_work_days": 4,
            },
            {
                "email": "worker03@example.com",
                "name": "三鷹瞬",
                "is_staff": False,
                "hire_date": date(2023, 10, 1),
                "weekly_work_days": 4,
            },
            {
                "email": "worker04@example.com",
                "name": "四谷",
                "is_staff": False,
                "hire_date": date(2024, 4, 1),
                "weekly_work_days": 3,
            },
            {
                "email": "worker05@example.com",
                "name": "五代裕作",
                "is_staff": False,
                "hire_date": date(2024, 4, 1),
                "weekly_work_days": 3,
            },
            {
                "email": "worker06@example.com",
                "name": "六本木朱美",
                "is_staff": False,
                "hire_date": date(2024, 10, 1),
                "weekly_work_days": 2,
            },
            {
                "email": "worker07@example.com",
                "name": "七尾こずえ",
                "is_staff": False,
                "hire_date": date(2024, 10, 1),
                "weekly_work_days": 2,
            },
            {
                "email": "worker08@example.com",
                "name": "八神いぶき",
                "is_staff": False,
                "hire_date": date(2025, 4, 1),
                "weekly_work_days": 1,
            },
        ]

        users = {}
        for user_data in users_data:
            # 既存ユーザーを取得、存在しない場合は作成
            user, created = User.objects.get_or_create(
                email=user_data["email"],
                defaults={
                    "name": user_data["name"],
                },
            )

            # 新規作成の場合のみパスワードを設定
            if created:
                user.set_password("motitasu")

            # ユーザー属性を更新
            user.is_staff = user_data["is_staff"]
            user.hire_date = user_data["hire_date"]
            user.weekly_work_days = user_data["weekly_work_days"]
            user.save()

            users[user_data["email"]] = user

        self.stdout.write(self.style.SUCCESS("✓ ユーザーデータの作成が完了しました"))
        return users

    def create_time_records(self, users):
        """タイムレコードを作成"""
        self.stdout.write("タイムレコードを作成中...")

        jst = ZoneInfo("Asia/Tokyo")
        today = date.today()

        # 店長のタイムレコード（9-18時、13-14時休憩）
        manager = users["owner01@example.com"]
        self.create_manager_time_records(manager, jst, today)

        # アルバイトのタイムレコード（15-18時）
        worker_emails = [
            "worker01@example.com",
            "worker02@example.com",
            "worker03@example.com",
            "worker04@example.com",
            "worker05@example.com",
            "worker06@example.com",
            "worker07@example.com",
            "worker08@example.com",
        ]
        for email in worker_emails:
            worker = users[email]
            self.create_worker_time_records(worker, jst, today)

        self.stdout.write(self.style.SUCCESS("✓ タイムレコードの作成が完了しました"))

    def create_manager_time_records(self, manager, jst, today):
        """店長のタイムレコードを作成"""
        current_date = manager.hire_date

        while current_date <= today:
            # 週の曜日を取得（0=月曜日）
            weekday = current_date.weekday()

            # 店長の週6勤務（日曜日休み、日曜日は6）
            if weekday != 6:
                # 9時出勤
                clock_in_time = datetime.combine(
                    current_date, datetime.min.time().replace(hour=9)
                )
                clock_in_time = clock_in_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=manager, clock_type="clock_in", timestamp=clock_in_time
                )

                # 13時休憩開始
                break_start_time = datetime.combine(
                    current_date, datetime.min.time().replace(hour=13)
                )
                break_start_time = break_start_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=manager, clock_type="break_start", timestamp=break_start_time
                )

                # 14時休憩終了
                break_end_time = datetime.combine(
                    current_date, datetime.min.time().replace(hour=14)
                )
                break_end_time = break_end_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=manager, clock_type="break_end", timestamp=break_end_time
                )

                # 18時退勤
                clock_out_time = datetime.combine(
                    current_date, datetime.min.time().replace(hour=18)
                )
                clock_out_time = clock_out_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=manager, clock_type="clock_out", timestamp=clock_out_time
                )

            current_date += timedelta(days=1)

    def create_worker_time_records(self, worker, jst, today):
        """アルバイトのタイムレコードを作成"""
        current_date = worker.hire_date

        while current_date <= today:
            weekday = current_date.weekday()

            # 週の所定労働日数に応じて勤務パターンを決定
            should_work = False
            if worker.weekly_work_days >= 5:
                should_work = weekday < worker.weekly_work_days
            elif worker.weekly_work_days == 4:  # 月火木金
                should_work = weekday in [0, 1, 3, 4]
            elif worker.weekly_work_days == 3:  # 月水金
                should_work = weekday in [0, 2, 4]
            elif worker.weekly_work_days == 2:  # 火木
                should_work = weekday in [1, 3]
            elif worker.weekly_work_days == 1:  # 金
                should_work = weekday == 4

            if should_work:
                # 15時出勤
                clock_in_time = datetime.combine(
                    current_date, datetime.min.time().replace(hour=15)
                )
                clock_in_time = clock_in_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=worker, clock_type="clock_in", timestamp=clock_in_time
                )

                # 18時退勤
                clock_out_time = datetime.combine(
                    current_date, datetime.min.time().replace(hour=18)
                )
                clock_out_time = clock_out_time.replace(tzinfo=jst)
                TimeRecord.objects.create(
                    user=worker, clock_type="clock_out", timestamp=clock_out_time
                )

            current_date += timedelta(days=1)

    def create_paid_leave_records(self, users):
        """有給休暇記録を作成"""
        self.stdout.write("有給休暇記録を作成中...")

        from timeclock.services.paid_leave_auto_processor import PaidLeaveAutoProcessor

        # 全ユーザーの最も古い入社日を取得
        earliest_hire_date = min(
            (user.hire_date for user in users.values() if user.hire_date),
            default=None
        )

        if earliest_hire_date:
            processor = PaidLeaveAutoProcessor()
            current_date = earliest_hire_date
            today = date.today()

            while current_date <= today:
                # 日次付与処理を実行（全ユーザーを一度に処理）
                processor.process_daily_grants_and_expirations(current_date)
                current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS("✓ 有給休暇記録の作成が完了しました"))

    def create_monthly_targets(self, users):
        """月別目標を作成"""
        self.stdout.write("月別目標を作成中...")

        user = users.get("worker01@example.com")
        if user:
            # 2025年9月の目標
            MonthlyTarget.objects.create(
                user=user, year=2025, month=9, target_income=100000
            )

            # 2025年10月の目標
            MonthlyTarget.objects.create(
                user=user, year=2025, month=10, target_income=100000
            )

        self.stdout.write(self.style.SUCCESS("✓ 月別目標の作成が完了しました"))

    def create_messages_and_reactions(self, users):
        """伝言板メッセージとリアクションを作成"""
        self.stdout.write("伝言板メッセージとリアクションを作成中...")

        jst = ZoneInfo("Asia/Tokyo")
        today = timezone.now().astimezone(jst)

        # メッセージデータ
        messages_data = [
            {
                "user": "owner01@example.com",
                "content": "来月のシフト締め切りが今週末です。みなさん忘れないようにー！",
                "show_name": True,
                "days_ago": 2,
                "is_pinned": True,
                "pin_duration_hours": 168,  # 1週間
            },
            {
                "user": "worker01@example.com",
                "content": "今日純売り上げが20万超えました！忙しかったですね。お疲れ様でした〜",
                "show_name": False,
                "days_ago": 4,
            },
            {
                "user": "worker02@example.com",
                "content": "明日オープンの方、サンドイッチの仕込み終わらなかったのでおねがします！すみません汗",
                "show_name": False,
                "days_ago": 6,
            },
            {
                "user": "worker03@example.com",
                "content": "風邪治りました！シフト変わってくださった方ありがとうございました！",
                "show_name": True,
                "days_ago": 8,
            },
            {
                "user": "worker04@example.com",
                "content": "駅前のパン屋さんの新商品美味しかったです！おすすめ♪",
                "show_name": False,
                "days_ago": 10,
            },
            {
                "user": "worker05@example.com",
                "content": "来週から新メニューですね。楽しみです！",
                "show_name": True,
                "days_ago": 12,
            },
            {
                "user": "owner01@example.com",
                "content": "エアコンの調子が悪いので業者に連絡しました。明日修理予定です。",
                "show_name": True,
                "days_ago": 14,
            },
            {
                "user": "worker01@example.com",
                "content": "今日のお客様、常連の○○さんがケーキを褒めてくださいました！嬉しい〜",
                "show_name": False,
                "days_ago": 16,
            },
        ]

        messages = []
        for msg_data in messages_data:
            user = users[msg_data["user"]]
            created_at = today - timedelta(days=msg_data["days_ago"])

            message = Message.objects.create(
                user=user,
                content=msg_data["content"],
                show_name=msg_data["show_name"],
                created_at=created_at,
            )

            # ピン留めメッセージの設定
            if msg_data.get("is_pinned"):
                message.pin_message(msg_data["pin_duration_hours"])

            messages.append(message)

        # リアクションデータ
        reactions_data = [
            # メッセージ1（シフト締切）：アルバイト1,2,3が👍
            {
                "message_idx": 0,
                "users": [
                    "worker01@example.com",
                    "worker02@example.com",
                    "worker03@example.com",
                ],
                "reaction": "thumbs_up",
            },
            # メッセージ2（売上20万）：店長が👍、アルバイト2,3が😮、デモ用01が❤️
            {
                "message_idx": 1,
                "users": ["owner01@example.com"],
                "reaction": "thumbs_up",
            },
            {
                "message_idx": 1,
                "users": ["worker02@example.com", "worker03@example.com"],
                "reaction": "surprised",
            },
            {"message_idx": 1, "users": ["worker04@example.com"], "reaction": "heart"},
            # メッセージ3（仕込み依頼）：アルバイト1が👍、店長が👍
            {
                "message_idx": 2,
                "users": ["worker01@example.com", "owner01@example.com"],
                "reaction": "thumbs_up",
            },
            # メッセージ4（風邪回復）：店長が❤️、アルバイト1,2が👍、デモ用01が😂
            {"message_idx": 3, "users": ["owner01@example.com"], "reaction": "heart"},
            {
                "message_idx": 3,
                "users": ["worker01@example.com", "worker02@example.com"],
                "reaction": "thumbs_up",
            },
            {
                "message_idx": 3,
                "users": ["worker05@example.com"],
                "reaction": "laughing",
            },
            # メッセージ5（パン屋情報）：アルバイト1,3が❤️、デモ用01が👍
            {
                "message_idx": 4,
                "users": ["worker01@example.com", "worker03@example.com"],
                "reaction": "heart",
            },
            {
                "message_idx": 4,
                "users": ["worker06@example.com"],
                "reaction": "thumbs_up",
            },
            # メッセージ6（新メニュー）：店長が👍、アルバイト2が❤️
            {
                "message_idx": 5,
                "users": ["owner01@example.com"],
                "reaction": "thumbs_up",
            },
            {"message_idx": 5, "users": ["worker02@example.com"], "reaction": "heart"},
            # メッセージ7（エアコン修理）：全員が👍
            {"message_idx": 6, "users": list(users.keys()), "reaction": "thumbs_up"},
            # メッセージ8（お客様の声）：店長が❤️、アルバイト2,3,4が👍、デモ用01が😂
            {"message_idx": 7, "users": ["owner01@example.com"], "reaction": "heart"},
            {
                "message_idx": 7,
                "users": [
                    "worker02@example.com",
                    "worker03@example.com",
                    "worker04@example.com",
                ],
                "reaction": "thumbs_up",
            },
            {
                "message_idx": 7,
                "users": ["worker07@example.com"],
                "reaction": "laughing",
            },
        ]

        for reaction_data in reactions_data:
            message = messages[reaction_data["message_idx"]]
            for user_email in reaction_data["users"]:
                user = users[user_email]
                try:
                    Reaction.objects.create(
                        user=user,
                        message=message,
                        reaction_type=reaction_data["reaction"],
                    )
                except Exception:
                    # 重複などのエラーは無視
                    pass

        self.stdout.write(
            self.style.SUCCESS("✓ 伝言板メッセージとリアクションの作成が完了しました")
        )

    def create_leaderboard_entries(self, users):
        """リーダーボードエントリを作成"""
        self.stdout.write("リーダーボードエントリを作成中...")

        from leaderboard.services.leaderboard_service import LeaderboardService

        today = date.today()
        current_year = today.year
        current_month = today.month

        # 前月の年月を計算
        if current_month == 1:
            previous_year = current_year - 1
            previous_month = 12
        else:
            previous_year = current_year
            previous_month = current_month - 1

        # 今月のエントリを作成（空のエントリを作成）店長は除外
        for user in users.values():
            if user.email == "owner01@example.com":
                continue
            LeaderboardEntry.objects.create(
                user=user,
                year=current_year,
                month=current_month,
                total_minutes=0,
                rank=None,
            )

        # 前月のエントリを作成（空のエントリを作成）店長は除外
        for user in users.values():
            if user.email == "owner01@example.com":
                continue
            LeaderboardEntry.objects.create(
                user=user,
                year=previous_year,
                month=previous_month,
                total_minutes=0,
                rank=None,
            )

        # 出勤記録から労働時間を再計算
        self.stdout.write("出勤記録から労働時間を再計算中...")

        # 今月分の再計算（店長は除外）
        for user in users.values():
            if user.email == "owner01@example.com":
                continue
            service = LeaderboardService(user)
            entry, _ = service.recalculate_user_stats_from_scratch(
                user=user, year=current_year, month=current_month
            )
            if entry:
                self.stdout.write(f"  {user.name}: {entry.total_hours_display}")

        # 今月のランキング更新
        service = LeaderboardService()
        service.update_leaderboard(current_year, current_month)

        # 前月分の再計算（店長は除外）
        for user in users.values():
            if user.email == "owner01@example.com":
                continue
            service = LeaderboardService(user)
            service.recalculate_user_stats_from_scratch(
                user=user, year=previous_year, month=previous_month
            )

        # 前月のランキング更新
        service.update_leaderboard(previous_year, previous_month)

        self.stdout.write(
            self.style.SUCCESS("✓ リーダーボードエントリの作成が完了しました")
        )

    def create_salary_data(self, users):
        """給与グレード・スキルデータを作成"""
        self.stdout.write("給与グレード・スキルデータを作成中...")

        manager = users["owner01@example.com"]

        # 1. Skillを作成
        self.stdout.write("  スキルを作成中...")
        skills_data = [
            {
                "name": "勤続1ヶ月",
                "category": "technical",
                "description": "勤続1ヶ月以上経過している",
            },
            {
                "name": "水出し",
                "category": "customer_service",
                "description": "お冷の提供、メニューや注文方法の案内ができる",
            },
            {
                "name": "オーダーテイク",
                "category": "customer_service",
                "description": "お客様のオーダーを正確に受けることができる",
            },
            {
                "name": "料理提供",
                "category": "customer_service",
                "description": "料理を適切にお客様へ提供できる",
            },
            {
                "name": "ご案内",
                "category": "customer_service",
                "description": "お客様を席へご案内できる",
            },
            {
                "name": "ドリンク提供",
                "category": "customer_service",
                "description": "ドリンクを適切に提供できる",
            },
            {
                "name": "会計",
                "category": "customer_service",
                "description": "レジ操作と会計処理ができる",
            },
            {
                "name": "レジ締め",
                "category": "customer_service",
                "description": "レジ締め作業ができる",
            },
            {
                "name": "ゴミ出し",
                "category": "customer_service",
                "description": "ゴミの分別と搬出ができる",
            },
            {
                "name": "客席掃除",
                "category": "customer_service",
                "description": "客席の清掃ができる",
            },
            {
                "name": "仕込み",
                "category": "technical",
                "description": "料理の仕込み作業ができる",
            },
            {
                "name": "料理",
                "category": "technical",
                "description": "基本的な調理ができる",
            },
            {
                "name": "迅速料理",
                "category": "technical",
                "description": "素早く正確な調理ができる",
            },
            {
                "name": "グリストラップ",
                "category": "technical",
                "description": "グリストラップの清掃ができる",
            },
            {
                "name": "洗い物",
                "category": "technical",
                "description": "食器の洗浄ができる",
            },
            {
                "name": "キッチン掃除",
                "category": "technical",
                "description": "キッチンの清掃ができる",
            },
            {
                "name": "発注",
                "category": "management",
                "description": "食材や備品の発注ができる",
            },
            {
                "name": "シフト作成",
                "category": "management",
                "description": "スタッフのシフトを作成できる",
            },
        ]

        skills = {}
        for skill_data in skills_data:
            skill = Skill.objects.create(**skill_data)
            skills[skill_data["name"]] = skill

        # 2. SalaryGradeを作成
        self.stdout.write("  給与グレードを作成中...")
        grades_data = [
            {
                "name": "研修生",
                "level": 0,
                "hourly_wage": 1100,
                "description": "職場になれる",
            },
            {
                "name": "ホール",
                "level": 1,
                "hourly_wage": 1200,
                "description": "基本的なホール業務をできる。ホールリーダーと共に店を回す。",
            },
            {
                "name": "ホールリーダー",
                "level": 2,
                "hourly_wage": 1350,
                "description": "ホール業務を全てできる。ホールと共に店を回す。",
            },
            {
                "name": "キッチン",
                "level": 1,
                "hourly_wage": 1200,
                "description": "基本的なキッチン業務を覚える。",
            },
            {
                "name": "キッチンリーダー",
                "level": 2,
                "hourly_wage": 1350,
                "description": "キッチン業務を全てできる。キッチンと共に店を回す。",
            },
            {
                "name": "オールラウンダー（ホール）",
                "level": 3,
                "hourly_wage": 1500,
                "description": "ホールとキッチンの両方ができる。",
            },
            {
                "name": "オールラウンダー（キッチン）",
                "level": 3,
                "hourly_wage": 1500,
                "description": "キッチンとホールの両方ができる。",
            },
            {
                "name": "マネージャー",
                "level": 4,
                "hourly_wage": 1700,
                "description": "店舗管理業務を行える。",
            },
        ]

        grades = {}
        for grade_data in grades_data:
            grade = SalaryGrade.objects.create(**grade_data)
            grades[grade_data["name"]] = grade

        # 3. SalaryGradeの必要スキルと昇進先を設定
        self.stdout.write("  給与グレードの関連情報を設定中...")

        # 研修生
        grades["研修生"].next_possible_grades.set(
            [grades["ホール"], grades["キッチン"]]
        )

        # ホール
        grades["ホール"].required_skills.set(
            [
                skills["勤続1ヶ月"],
                skills["水出し"],
                skills["オーダーテイク"],
                skills["料理提供"],
                skills["ゴミ出し"],
                skills["客席掃除"],
                skills["洗い物"],
            ]
        )
        grades["ホール"].next_possible_grades.set(
            [grades["ホールリーダー"], grades["キッチン"]]
        )

        # ホールリーダー
        grades["ホールリーダー"].required_skills.set(
            [
                skills["勤続1ヶ月"],
                skills["水出し"],
                skills["オーダーテイク"],
                skills["料理提供"],
                skills["ゴミ出し"],
                skills["客席掃除"],
                skills["洗い物"],
                skills["会計"],
                skills["レジ締め"],
                skills["ご案内"],
                skills["ドリンク提供"],
            ]
        )
        grades["ホールリーダー"].next_possible_grades.set(
            [grades["オールラウンダー（ホール）"]]
        )

        # キッチン
        grades["キッチン"].required_skills.set(
            [
                skills["勤続1ヶ月"],
                skills["仕込み"],
                skills["料理"],
                skills["グリストラップ"],
                skills["洗い物"],
                skills["キッチン掃除"],
            ]
        )
        grades["キッチン"].next_possible_grades.set(
            [grades["キッチンリーダー"], grades["ホール"]]
        )

        # キッチンリーダー
        grades["キッチンリーダー"].required_skills.set(
            [
                skills["勤続1ヶ月"],
                skills["仕込み"],
                skills["料理"],
                skills["グリストラップ"],
                skills["洗い物"],
                skills["キッチン掃除"],
                skills["迅速料理"],
            ]
        )
        grades["キッチンリーダー"].next_possible_grades.set(
            [grades["オールラウンダー（キッチン）"]]
        )

        # オールラウンダー（ホール）
        grades["オールラウンダー（ホール）"].required_skills.set(
            [
                skills["勤続1ヶ月"],
                skills["水出し"],
                skills["オーダーテイク"],
                skills["料理提供"],
                skills["ゴミ出し"],
                skills["客席掃除"],
                skills["洗い物"],
                skills["会計"],
                skills["レジ締め"],
                skills["ご案内"],
                skills["ドリンク提供"],
                skills["仕込み"],
                skills["料理"],
                skills["グリストラップ"],
                skills["キッチン掃除"],
            ]
        )
        grades["オールラウンダー（ホール）"].next_possible_grades.set(
            [grades["マネージャー"]]
        )

        # オールラウンダー（キッチン）
        grades["オールラウンダー（キッチン）"].required_skills.set(
            [
                skills["勤続1ヶ月"],
                skills["仕込み"],
                skills["料理"],
                skills["グリストラップ"],
                skills["洗い物"],
                skills["キッチン掃除"],
                skills["迅速料理"],
                skills["水出し"],
                skills["オーダーテイク"],
                skills["料理提供"],
                skills["ゴミ出し"],
                skills["客席掃除"],
            ]
        )
        grades["オールラウンダー（キッチン）"].next_possible_grades.set(
            [grades["マネージャー"]]
        )

        # マネージャー
        grades["マネージャー"].required_skills.set(
            [skills["発注"], skills["シフト作成"]]
        )

        # 4. 各ユーザーのUserSkillとUserSalaryGradeを作成
        self.stdout.write("  ユーザーのスキル・グレードを設定中...")

        # 音無響子（店長）- マネージャー、全スキル習得
        for skill in skills.values():
            UserSkill.objects.create(
                user=manager,
                skill=skill,
                acquired_date=manager.hire_date,
                approved_by=manager,
            )
        UserSalaryGrade.objects.create(
            user=manager,
            salary_grade=grades["マネージャー"],
            effective_date=manager.hire_date,
            changed_by=manager,
            reason="店長として採用",
        )

        # 一の瀬花枝 - ホール
        worker01 = users["worker01@example.com"]
        worker01_skills = [
            "勤続1ヶ月",
            "水出し",
            "オーダーテイク",
            "料理提供",
            "ゴミ出し",
            "客席掃除",
            "洗い物",
            "会計",
        ]
        for skill_name in worker01_skills:
            UserSkill.objects.create(
                user=worker01,
                skill=skills[skill_name],
                acquired_date=worker01.hire_date + timedelta(days=30),
                approved_by=manager,
            )
        UserSalaryGrade.objects.create(
            user=worker01,
            salary_grade=grades["ホール"],
            effective_date=worker01.hire_date + timedelta(days=30),
            changed_by=manager,
            reason="ホール業務習得",
        )
        # 申告中スキル：レジ締め
        SkillApplication.objects.create(
            user=worker01,
            skill=skills["レジ締め"],
            status="pending",
            comment="レジ締め作業を覚えました",
        )

        # 二階堂望 - ホールリーダー
        worker02 = users["worker02@example.com"]
        worker02_skills = [
            "勤続1ヶ月",
            "水出し",
            "オーダーテイク",
            "料理提供",
            "ゴミ出し",
            "客席掃除",
            "洗い物",
            "会計",
            "レジ締め",
            "ご案内",
            "ドリンク提供",
        ]
        for skill_name in worker02_skills:
            UserSkill.objects.create(
                user=worker02,
                skill=skills[skill_name],
                acquired_date=worker02.hire_date + timedelta(days=60),
                approved_by=manager,
            )
        UserSalaryGrade.objects.create(
            user=worker02,
            salary_grade=grades["ホールリーダー"],
            effective_date=worker02.hire_date + timedelta(days=60),
            changed_by=manager,
            reason="ホールリーダー昇格",
        )
        # 申告中スキル：仕込み
        SkillApplication.objects.create(
            user=worker02,
            skill=skills["仕込み"],
            status="pending",
            comment="仕込み作業を覚えました",
        )

        # 三鷹瞬 - キッチン
        worker03 = users["worker03@example.com"]
        worker03_skills = [
            "勤続1ヶ月",
            "仕込み",
            "料理",
            "グリストラップ",
            "洗い物",
            "キッチン掃除",
        ]
        for skill_name in worker03_skills:
            UserSkill.objects.create(
                user=worker03,
                skill=skills[skill_name],
                acquired_date=worker03.hire_date + timedelta(days=30),
                approved_by=manager,
            )
        UserSalaryGrade.objects.create(
            user=worker03,
            salary_grade=grades["キッチン"],
            effective_date=worker03.hire_date + timedelta(days=30),
            changed_by=manager,
            reason="キッチン業務習得",
        )
        # 申告中スキル：迅速料理
        SkillApplication.objects.create(
            user=worker03,
            skill=skills["迅速料理"],
            status="pending",
            comment="素早く調理できるようになりました",
        )

        # 四谷 - キッチンリーダー
        worker04 = users["worker04@example.com"]
        worker04_skills = [
            "勤続1ヶ月",
            "仕込み",
            "料理",
            "グリストラップ",
            "洗い物",
            "キッチン掃除",
            "迅速料理",
        ]
        for skill_name in worker04_skills:
            UserSkill.objects.create(
                user=worker04,
                skill=skills[skill_name],
                acquired_date=worker04.hire_date + timedelta(days=90),
                approved_by=manager,
            )
        UserSalaryGrade.objects.create(
            user=worker04,
            salary_grade=grades["キッチンリーダー"],
            effective_date=worker04.hire_date + timedelta(days=90),
            changed_by=manager,
            reason="キッチンリーダー昇格",
        )
        # 申告中スキル：水出し
        SkillApplication.objects.create(
            user=worker04,
            skill=skills["水出し"],
            status="pending",
            comment="ホール業務も覚えたいです",
        )

        # 五代裕作 - オールラウンダー（キッチン）
        worker05 = users["worker05@example.com"]
        worker05_skills = [
            "勤続1ヶ月",
            "仕込み",
            "料理",
            "グリストラップ",
            "洗い物",
            "キッチン掃除",
            "迅速料理",
            "水出し",
            "オーダーテイク",
            "料理提供",
            "ゴミ出し",
            "客席掃除",
        ]
        for skill_name in worker05_skills:
            UserSkill.objects.create(
                user=worker05,
                skill=skills[skill_name],
                acquired_date=worker05.hire_date + timedelta(days=120),
                approved_by=manager,
            )
        UserSalaryGrade.objects.create(
            user=worker05,
            salary_grade=grades["オールラウンダー（キッチン）"],
            effective_date=worker05.hire_date + timedelta(days=120),
            changed_by=manager,
            reason="オールラウンダー昇格",
        )
        # 申告中スキル：発注
        SkillApplication.objects.create(
            user=worker05,
            skill=skills["発注"],
            status="pending",
            comment="発注業務を覚えました",
        )

        # 六本木朱美 - オールラウンダー（ホール）
        worker06 = users["worker06@example.com"]
        worker06_skills = [
            "勤続1ヶ月",
            "水出し",
            "オーダーテイク",
            "料理提供",
            "ゴミ出し",
            "客席掃除",
            "洗い物",
            "会計",
            "レジ締め",
            "ご案内",
            "ドリンク提供",
            "仕込み",
            "料理",
            "グリストラップ",
            "キッチン掃除",
        ]
        for skill_name in worker06_skills:
            UserSkill.objects.create(
                user=worker06,
                skill=skills[skill_name],
                acquired_date=worker06.hire_date + timedelta(days=120),
                approved_by=manager,
            )
        UserSalaryGrade.objects.create(
            user=worker06,
            salary_grade=grades["オールラウンダー（ホール）"],
            effective_date=worker06.hire_date + timedelta(days=120),
            changed_by=manager,
            reason="オールラウンダー昇格",
        )
        # 申告中スキル：シフト作成
        SkillApplication.objects.create(
            user=worker06,
            skill=skills["シフト作成"],
            status="pending",
            comment="シフト作成を手伝いたいです",
        )

        # 七尾こずえ - 研修生
        worker07 = users["worker07@example.com"]
        UserSalaryGrade.objects.create(
            user=worker07,
            salary_grade=grades["研修生"],
            effective_date=worker07.hire_date,
            changed_by=manager,
            reason="研修生として採用",
        )

        # 八神いぶき - 研修生
        worker08 = users["worker08@example.com"]
        UserSalaryGrade.objects.create(
            user=worker08,
            salary_grade=grades["研修生"],
            effective_date=worker08.hire_date,
            changed_by=manager,
            reason="研修生として採用",
        )

        self.stdout.write(
            self.style.SUCCESS("✓ 給与グレード・スキルデータの作成が完了しました")
        )
