# 伝言板機能 設計書

## 概要
任意のユーザーがメッセージを投稿し、他のユーザーがそれを閲覧・リアクションできる伝言板機能を実装する。

## 機能要件

### 1. メッセージ投稿機能
- ログインユーザーがメッセージを投稿できる
- メッセージは最新順でトップページに表示される
- 投稿者名とタイムスタンプが表示される

### 2. メッセージ閲覧機能  
- ログインユーザーがメッセージを閲覧できる
- メッセージ一覧はページネーション対応
- 最新のメッセージが上部に表示される
- ピン留めされたメッセージは上部に固定表示される

### 3. リアクション機能
- ログインユーザーがメッセージにリアクション（スタンプ）を付けられる
- リアクション種類：👍（いいね）、❤️（ハート）、😂（笑い）、😮（驚き）
- 管理者はリアクション種類をカスタマイズで追加も可能
- 同一ユーザーは同一メッセージに対して各リアクション種類を1回のみ設定可能
- リアクション数がメッセージと一緒に表示される
- リアクションしたユーザー一覧を表示できる

### 4. ピン留め機能
- 任意のユーザーは自身の投稿したメッセージをピン留めできる
- ピン留め期間：12時間、24時間、1週間の3つから選択可能
- ピン留めされたメッセージは通常のメッセージより上部に固定表示される
- ピン留めされたメッセージ同士の表示順序：
  - 固定時間が長いものを優先（1週間 > 24時間 > 12時間）
  - 固定時間が同じ場合は、ピン留めされたタイミングが後のものを優先
- ピン留め期間終了後は自動的に通常表示に戻る
- ユーザーは任意のタイミングでピン留めを解除できる

### 5. 権限管理
- メッセージの投稿：ログインユーザーのみ
- メッセージの閲覧：ログインユーザーのみ
- リアクション：ログインユーザーのみ
- ピン留め：投稿者本人のみ（自分の投稿のみ）
- リアクションのカスタマイズ：管理者のみ

## データモデル設計

### 1. Message モデル
```python
class Message(models.Model):
    """伝言板メッセージ"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='投稿者'
    )
    content = models.TextField(
        verbose_name='メッセージ内容',
        max_length=200,
        help_text='メッセージ内容を入力してください（最大200文字）'
    )
    is_pinned = models.BooleanField(
        verbose_name='ピン留め',
        default=False,
        help_text='このメッセージがピン留めされているかどうか'
    )
    pin_duration_hours = models.PositiveIntegerField(
        verbose_name='ピン留め期間（時間）',
        null=True,
        blank=True,
        choices=[
            (12, '12時間'),
            (24, '24時間'),
            (168, '1週間'),  # 7日 × 24時間 = 168時間
        ],
        help_text='ピン留め期間を時間単位で指定'
    )
    pinned_at = models.DateTimeField(
        verbose_name='ピン留め日時',
        null=True,
        blank=True,
        help_text='ピン留めされた日時'
    )
    pin_expires_at = models.DateTimeField(
        verbose_name='ピン留め期限',
        null=True,
        blank=True,
        help_text='ピン留めが自動解除される日時'
    )
    created_at = models.DateTimeField(
        verbose_name='投稿日時',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        verbose_name='更新日時',
        auto_now=True
    )
    
    class Meta:
        verbose_name = 'メッセージ'
        verbose_name_plural = 'メッセージ'
        ordering = [
            '-is_pinned',  # ピン留めメッセージを上位に
            '-pin_duration_hours',  # ピン留め期間が長い順
            '-pinned_at',  # ピン留め日時が新しい順
            '-created_at'  # 通常の投稿日時順
        ]
        
    def __str__(self):
        return f"{self.user.name}: {self.content[:50]}..."
        
    def get_reaction_counts(self):
        """各リアクションの数を取得"""
        from django.db.models import Count
        return self.reactions.values('reaction_type').annotate(count=Count('reaction_type'))
        
    def is_pin_expired(self):
        """ピン留めが期限切れかどうかを判定"""
        if not self.is_pinned or not self.pin_expires_at:
            return False
        from django.utils import timezone
        import pytz
        jst = pytz.timezone('Asia/Tokyo')
        return timezone.now().astimezone(jst) > self.pin_expires_at
        
    def pin_message(self, duration_hours):
        """メッセージをピン留めする"""
        from django.utils import timezone
        from datetime import timedelta
        import pytz
        
        jst = pytz.timezone('Asia/Tokyo')
        self.is_pinned = True
        self.pin_duration_hours = duration_hours
        self.pinned_at = timezone.now().astimezone(jst)
        self.pin_expires_at = self.pinned_at + timedelta(hours=duration_hours)
        self.save()
        
    def unpin_message(self):
        """ピン留めを解除する"""
        self.is_pinned = False
        self.pin_duration_hours = None
        self.pinned_at = None
        self.pin_expires_at = None
        self.save()
        
    def get_pin_remaining_time(self):
        """ピン留めの残り時間を取得（秒単位）"""
        if not self.is_pinned or not self.pin_expires_at:
            return 0
        from django.utils import timezone
        import pytz
        jst = pytz.timezone('Asia/Tokyo')
        remaining = self.pin_expires_at - timezone.now().astimezone(jst)
        return max(0, remaining.total_seconds())
```

### 2. Reaction モデル
```python
class Reaction(models.Model):
    """メッセージリアクション"""
    
    REACTION_CHOICES = [
        ('thumbs_up', '👍'),
        ('heart', '❤️'),
        ('laughing', '😂'),
        ('surprised', '😮'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name='リアクションユーザー'
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name='対象メッセージ'
    )
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_CHOICES,
        verbose_name='リアクション種類'
    )
    created_at = models.DateTimeField(
        verbose_name='リアクション日時',
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = 'リアクション'
        verbose_name_plural = 'リアクション'
        unique_together = ('user', 'message', 'reaction_type')  # 同一ユーザー・同一メッセージ・同一種類の重複防止
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.name} → {self.get_reaction_type_display()} → {self.message.content[:30]}"
        
    def get_emoji(self):
        """絵文字を取得"""
        return dict(self.REACTION_CHOICES)[self.reaction_type]
```

## URL設計

### URLパターン
```python
# bulletin_board/urls.py
urlpatterns = [
    path('', views.message_list, name='message_list'),           # メッセージ一覧・投稿
    path('message/<int:message_id>/', views.message_detail, name='message_detail'),  # メッセージ詳細
    path('api/reaction/', views.toggle_reaction, name='toggle_reaction'),           # リアクション切り替えAPI
    path('api/reaction-users/<int:message_id>/<str:reaction_type>/', views.get_reaction_users, name='get_reaction_users'),  # リアクションユーザー一覧API
    path('api/pin/', views.toggle_pin, name='toggle_pin'),                         # ピン留め切り替えAPI
    path('api/pin-status/<int:message_id>/', views.get_pin_status, name='get_pin_status'),  # ピン留め状態取得API
]
```

### メインURL統合
```python
# motitasu/urls.py に追加
path('bulletin/', include('bulletin_board.urls')),
```

## ビュー設計

### 1. メッセージ一覧・投稿ビュー
```python
@login_required
def message_list(request):
    """メッセージ一覧表示・投稿処理"""
    
    if request.method == 'POST':
        # メッセージ投稿処理
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(user=request.user, content=content)
            messages.success(request, 'メッセージを投稿しました。')
        else:
            messages.error(request, 'メッセージ内容を入力してください。')
        return redirect('message_list')
    
    # メッセージ一覧取得（ページング対応）
    message_list = Message.objects.select_related('user').prefetch_related('reactions')
    paginator = Paginator(message_list, 20)  # 20件ずつ表示
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 各メッセージのリアクション情報を整理
    for message in page_obj:
        message.reaction_summary = get_reaction_summary(message)
        if request.user.is_authenticated:
            message.user_reactions = get_user_reactions(message, request.user)
    
    context = {
        'page_obj': page_obj,
        'reaction_choices': Reaction.REACTION_CHOICES,
    }
    
    return render(request, 'bulletin_board/message_list.html', context)
```

### 2. リアクション切り替えAPI
```python
@login_required
@require_POST
def toggle_reaction(request):
    """リアクションの切り替え（Ajax API）"""
    
    try:
        message_id = request.POST.get('message_id')
        reaction_type = request.POST.get('reaction_type')
        
        message = Message.objects.get(id=message_id)
        
        # 既存リアクションを確認
        existing_reaction = Reaction.objects.filter(
            user=request.user,
            message=message,
            reaction_type=reaction_type
        ).first()
        
        if existing_reaction:
            # 既存リアクションを削除
            existing_reaction.delete()
            action = 'removed'
        else:
            # 新規リアクションを作成
            Reaction.objects.create(
                user=request.user,
                message=message,
                reaction_type=reaction_type
            )
            action = 'added'
        
        # 更新後のリアクション数を取得
        reaction_count = message.reactions.filter(reaction_type=reaction_type).count()
        
        return JsonResponse({
            'success': True,
            'action': action,
            'reaction_count': reaction_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
```

### 3. リアクションユーザー一覧API
```python
def get_reaction_users(request, message_id, reaction_type):
    """特定リアクションをしたユーザー一覧を取得"""
    import pytz
    
    try:
        message = Message.objects.get(id=message_id)
        reactions = message.reactions.filter(reaction_type=reaction_type).select_related('user')
        
        jst = pytz.timezone('Asia/Tokyo')
        user_list = [
            {
                'name': reaction.user.name,
                'created_at': reaction.created_at.astimezone(jst).strftime('%Y-%m-%d %H:%M')
            }
            for reaction in reactions
        ]
        
        return JsonResponse({
            'success': True,
            'users': user_list,
            'emoji': dict(Reaction.REACTION_CHOICES)[reaction_type]
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
```

### 4. ピン留め切り替えAPI
```python
@login_required
@require_POST
def toggle_pin(request):
    """ピン留めの切り替え（Ajax API）"""
    import pytz
    
    try:
        message_id = request.POST.get('message_id')
        action = request.POST.get('action')  # 'pin' or 'unpin'
        
        message = Message.objects.get(id=message_id, user=request.user)  # 自分の投稿のみ
        jst = pytz.timezone('Asia/Tokyo')
        
        if action == 'pin':
            duration = int(request.POST.get('duration', 24))  # デフォルト24時間
            if duration not in [12, 24, 168]:
                duration = 24
            
            message.pin_message(duration)
            return JsonResponse({
                'success': True,
                'action': 'pinned',
                'duration': duration,
                'expires_at': message.pin_expires_at.astimezone(jst).isoformat()
            })
            
        elif action == 'unpin':
            message.unpin_message()
            return JsonResponse({
                'success': True,
                'action': 'unpinned'
            })
        
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            })
        
    except Message.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'メッセージが見つからないか、編集権限がありません。'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
```

### 5. ピン留め状態取得API
```python
def get_pin_status(request, message_id):
    """ピン留め状態を取得"""
    import pytz
    
    try:
        message = Message.objects.get(id=message_id)
        jst = pytz.timezone('Asia/Tokyo')
        
        return JsonResponse({
            'success': True,
            'is_pinned': message.is_pinned,
            'pin_duration_hours': message.pin_duration_hours,
            'pinned_at': message.pinned_at.astimezone(jst).isoformat() if message.pinned_at else None,
            'pin_expires_at': message.pin_expires_at.astimezone(jst).isoformat() if message.pin_expires_at else None,
            'remaining_seconds': message.get_pin_remaining_time(),
            'is_expired': message.is_pin_expired()
        })
        
    except Message.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'メッセージが見つかりません。'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
```

### 6. ヘルパー関数
```python
def get_reaction_summary(message):
    """メッセージのリアクション数を取得"""
    reaction_counts = message.get_reaction_counts()
    summary = {}
    for reaction in reaction_counts:
        summary[reaction['reaction_type']] = reaction['count']
    return summary

def get_user_reactions(message, user):
    """ユーザーがしたリアクションの一覧を取得"""
    user_reactions = message.reactions.filter(user=user)
    return [reaction.reaction_type for reaction in user_reactions]
```

### 7. 自動ピン留め解除タスク用マネジメントコマンド
```python
# bulletin_board/management/commands/cleanup_expired_pins.py
from django.core.management.base import BaseCommand
from django.utils import timezone
import pytz
from bulletin_board.models import Message

class Command(BaseCommand):
    help = '期限切れのピン留めメッセージを自動解除'
    
    def handle(self, *args, **options):
        jst = pytz.timezone('Asia/Tokyo')
        now = timezone.now().astimezone(jst)
        expired_messages = Message.objects.filter(
            is_pinned=True,
            pin_expires_at__lte=now
        )
        
        count = 0
        for message in expired_messages:
            message.unpin_message()
            count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'成功: {count}件の期限切れピン留めを解除しました。')
        )
```

## テンプレート設計

### 1. メッセージ一覧テンプレート
```html
<!-- templates/bulletin_board/message_list.html -->
{% extends 'base.html' %}
{% load tz %}

{% block title %}伝言板 - Motitasu{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'bulletin_board/css/bulletin_board.css' %}">
{% endblock %}

{% block content %}
<div class="container mt-4">
    <h2>伝言板</h2>
    
    <!-- メッセージ投稿フォーム -->
    {% if user.is_authenticated %}
    <div class="card mb-4">
        <div class="card-body">
            <form method="post">
                {% csrf_token %}
                <div class="mb-3">
                    <textarea class="form-control" name="content" rows="3" placeholder="メッセージを入力してください..." maxlength="1000" required></textarea>
                </div>
                <button type="submit" class="btn btn-primary">投稿</button>
            </form>
        </div>
    </div>
    {% endif %}
    
    <!-- メッセージ一覧 -->
    <div id="message-list">
        {% for message in page_obj %}
        <div class="card mb-3">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <strong>{{ message.user.name }}</strong>
                    {% timezone "Asia/Tokyo" %}
                    <small class="text-muted">{{ message.created_at|date:"Y年m月d日 H:i" }}</small>
                    {% endtimezone %}
                </div>
                <p class="card-text">{{ message.content|linebreaks }}</p>
                
                <!-- リアクションエリア -->
                <div class="reaction-area" data-message-id="{{ message.id }}">
                    {% for reaction_type, emoji in reaction_choices %}
                    <button class="reaction-btn btn btn-outline-secondary btn-sm me-1 mb-1" 
                            data-reaction-type="{{ reaction_type }}"
                            {% if not user.is_authenticated %}disabled{% endif %}>
                        {{ emoji }}
                        <span class="reaction-count">{{ message.reaction_summary|get_item:reaction_type|default:0 }}</span>
                    </button>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% empty %}
        <div class="alert alert-info">
            まだメッセージがありません。
        </div>
        {% endfor %}
    </div>
    
    <!-- ページング -->
    {% if page_obj.has_other_pages %}
    <nav aria-label="ページング">
        <ul class="pagination justify-content-center">
            {% if page_obj.has_previous %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.previous_page_number }}">前へ</a>
            </li>
            {% endif %}
            
            {% for num in page_obj.paginator.page_range %}
                {% if page_obj.number == num %}
                <li class="page-item active">
                    <span class="page-link">{{ num }}</span>
                </li>
                {% else %}
                <li class="page-item">
                    <a class="page-link" href="?page={{ num }}">{{ num }}</a>
                </li>
                {% endif %}
            {% endfor %}
            
            {% if page_obj.has_next %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.next_page_number }}">次へ</a>
            </li>
            {% endif %}
        </ul>
    </nav>
    {% endif %}
</div>
{% endblock %}

{% block extra_js %}
<script src="{% static 'bulletin_board/js/bulletin_board.js' %}"></script>
{% endblock %}
```

### 2. JavaScript設計
```javascript
// static/bulletin_board/js/bulletin_board.js
document.addEventListener('DOMContentLoaded', function() {
    // リアクションボタンのクリックイベント
    document.querySelectorAll('.reaction-btn').forEach(button => {
        button.addEventListener('click', function() {
            const messageId = this.closest('.reaction-area').dataset.messageId;
            const reactionType = this.dataset.reactionType;
            
            fetch('/bulletin/api/reaction/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCsrfToken()
                },
                body: `message_id=${messageId}&reaction_type=${reactionType}`
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // リアクション数を更新
                    const countSpan = this.querySelector('.reaction-count');
                    countSpan.textContent = data.reaction_count;
                    
                    // ボタンのスタイルを更新
                    if (data.action === 'added') {
                        this.classList.remove('btn-outline-secondary');
                        this.classList.add('btn-secondary');
                    } else {
                        this.classList.remove('btn-secondary');
                        this.classList.add('btn-outline-secondary');
                    }
                } else {
                    alert('エラーが発生しました: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('通信エラーが発生しました');
            });
        });
    });
});

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}
```

## CSS設計
```css
/* static/bulletin_board/css/bulletin_board.css */
.reaction-area {
    border-top: 1px solid #e9ecef;
    padding-top: 0.75rem;
    margin-top: 1rem;
}

.reaction-btn {
    font-size: 0.875rem;
    padding: 0.25rem 0.5rem;
    border-radius: 1rem;
    transition: all 0.2s ease;
}

.reaction-btn:hover {
    transform: scale(1.05);
}

.reaction-count {
    font-size: 0.75rem;
    margin-left: 0.25rem;
}

.message-card {
    transition: box-shadow 0.2s ease;
}

.message-card:hover {
    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
}
```

## 管理画面設定
```python
# bulletin_board/admin.py
from django.contrib import admin
from .models import Message, Reaction

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_preview', 'is_pinned', 'pin_duration_hours', 'created_at')
    list_filter = ('created_at', 'user', 'is_pinned', 'pin_duration_hours')
    search_fields = ('content', 'user__name')
    readonly_fields = ('created_at', 'updated_at', 'pinned_at', 'pin_expires_at')
    actions = ['bulk_unpin_messages']
    
    def bulk_unpin_messages(self, request, queryset):
        """選択したメッセージのピン留めを一括解除"""
        count = 0
        for message in queryset.filter(is_pinned=True):
            message.unpin_message()
            count += 1
        self.message_user(request, f'{count}件のピン留めを解除しました。')
    bulk_unpin_messages.short_description = '選択したメッセージのピン留めを解除'
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'メッセージ内容'

@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_preview', 'get_emoji', 'created_at')
    list_filter = ('reaction_type', 'created_at')
    search_fields = ('user__name', 'message__content')
    
    def message_preview(self, obj):
        return obj.message.content[:30] + "..." if len(obj.message.content) > 30 else obj.message.content
    message_preview.short_description = 'メッセージ'
```

## バッチ処理設定

### 1. 定期タスク設定（crontab）
```bash
# 期限切れピン留めの自動解除（本番環境）
# 斯分実行
*/5 * * * * cd /path/to/motitasu && python manage.py cleanup_expired_pins

# テスト環境用（時間実行）
0 * * * * cd /path/to/motitasu && python manage.py cleanup_expired_pins
```

### 2. Django設定でのスケジューラ対応
```python
# settings.py
INSTALLED_APPS = [
    # ...
    'django_crontab',  # django-crontabパッケージ使用時
    'bulletin_board',
    # ...
]

# タイムゾーン設定（JST）
TIME_ZONE = 'Asia/Tokyo'
USE_TZ = True

# Crontab設定
CRONTAB_JOBS = [
    ('*/5 * * * *', 'bulletin_board.cron.cleanup_expired_pins'),
]
```

## 実装順序
1. Djangoアプリ作成（`python manage.py startapp bulletin_board`）
2. モデル実装・マイグレーション
3. 管理画面設定
4. URL設定
5. ビュー実装（ピン留め機能、無限スクロール、API含む）
6. テンプレート実装（ポストイットデザイン、レスポンシブ対応）
7. 静的ファイル（CSS/JS）実装（ポストイットスタイル、無限スクロール機能）
8. メインnavigationに伝言板リンク追加
9. マネジメントコマンド実装（ピン留め自動解除）
10. 定期タスク設定（crontabまたはスケジューラ）

## セキュリティ考慮事項
- CSRFトークンの適切な使用
- XSS対策（テンプレート内での適切なエスケープ）
- SQLインジェクション対策（ORMの適切な使用）
- ログインユーザーのみの投稿・リアクション制限

## パフォーマンス考慮事項
- select_related/prefetch_relatedの活用
- 無限スクロールによる効率的なデータ読み込み
- Ajaxによる部分更新（リアクション、ピン留め）
- データベースインデックスの適切な設定（is_pinned, created_at, pin_expires_at）
- メッセージ取得のバッチ処理（20件ずつ）
- CSSアニメーションの最適化（transform, transition）

## ユーザビリティ考慮事項
- レスポンシブデザイン（スマートフォン対応）
- ポストイットの視覚的多様性（色、回転角度のバリエーション）
- ローディング状態の明確な表示
- エラーメッセージのユーザーフレンドリーな表示
- アクセシビリティ配慮（aria-label、キーボードナビゲーション）