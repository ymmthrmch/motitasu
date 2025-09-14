from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from zoneinfo import ZoneInfo
from bulletin_board.models import Message


class Command(BaseCommand):
    help = '期限切れのピン留めメッセージを自動解除'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の処理は行わず、対象となるメッセージを表示するのみ',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='詳細な実行ログを表示',
        )
    
    def handle(self, *args, **options):
        jst = ZoneInfo(settings.TIME_ZONE)
        now = timezone.now().astimezone(jst)
        
        # 期限切れのピン留めメッセージを取得
        expired_messages = Message.objects.filter(
            is_pinned=True,
            pin_expires_at__lte=now
        ).select_related('user')
        
        count = expired_messages.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('期限切れのピン留めメッセージはありません。')
            )
            return
        
        if options['verbose'] or options['dry_run']:
            self.stdout.write(f'対象メッセージ数: {count}件')
            self.stdout.write('=' * 50)
        
        processed_count = 0
        for message in expired_messages:
            if options['verbose'] or options['dry_run']:
                self.stdout.write(
                    f'ID: {message.id} | '
                    f'投稿者: {message.user.name} | '
                    f'期限: {message.pin_expires_at.strftime("%Y-%m-%d %H:%M")} | '
                    f'内容: {message.content[:30]}...'
                )
            
            if not options['dry_run']:
                # ピン留めを解除
                message.unpin_message()
                processed_count += 1
                
                if options['verbose']:
                    self.stdout.write(
                        f'  → ピン留めを解除しました'
                    )
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'[DRY RUN] {count}件の期限切れピン留めが解除対象です。')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'成功: {processed_count}件の期限切れピン留めを解除しました。')
            )
            
            if options['verbose']:
                self.stdout.write('=' * 50)
                self.stdout.write(f'処理完了時刻: {now.strftime("%Y-%m-%d %H:%M:%S")} JST')