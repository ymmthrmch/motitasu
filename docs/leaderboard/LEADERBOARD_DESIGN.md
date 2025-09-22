# リーダーボード機能設計書

## 1. アプリケーション概要

### 1.1 機能概要
月次労働時間リーダーボード機能は、従業員間の健全な競争を促進し、労働時間の可視化を通じてモチベーション向上を図るシステムです。

### 1.2 主要機能
- 月次労働時間リーダーボード表示
- リーダーボード参加申請機能
- リアルタイムリーダーボード更新
- 日次バッチ処理による再計算
- 参加者限定アクセス制御

## 2. 要件定義

### 2.1 機能要件

#### 2.1.1 リーダーボード参加
- **参加期間**: 毎月1日〜10日まで
- **参加方法**: 任意参加（オプトイン）
- **参加条件**: 有効な従業員アカウント
- **参加状態**: 月ごとに独立（毎月新規申請必要）

#### 2.1.2 リーダーボード計算
- **対象期間**: 当月1日00:00〜月末日23:59
- **計算基準**: 総労働時間（出勤〜退勤の合計）
- **更新タイミング**: 
  - 退勤打刻時（リアルタイム）
  - 日次バッチ処理（AM 1:00）
- **表示順序**: 労働時間降順

#### 2.1.3 閲覧権限
- **閲覧可能**: 当月参加者のみ
- **閲覧不可**: 未参加者
- **表示内容**: 順位、氏名、労働時間

## 3. システム設計

### 3.1 アプリケーション構成

```
leaderboard/
├── models.py          # データモデル
├── views.py           # ビューロジック
├── urls.py            # URLルーティング
├── admin.py           # 管理画面
├── apps.py            # アプリ設定
├── management/
│   └── commands/
│       └── update_leaderboard.py  # バッチ処理
└── tests/
    ├── test_models.py
    ├── test_views.py
    └── test_commands.py

# テンプレートは以下に配置
templates/
└── leaderboard/
    ├── leaderboard_list.html
    ├── leaderboard_join.html
    └── leaderboard_detail.html

# 静的ファイルは以下に配置
static/
└── leaderboard/
    ├── css/
    │   └── leaderboard.css
    └── js/
        └── leaderboard.js
```

### 3.2 データベース設計

#### 3.2.1 LeaderboardEntry（リーダーボード参加記録）
```python
class LeaderboardEntry(models.Model):
    """
    リーダーボードへの参加記録と成績を管理
    月ごとの参加状況と労働時間、順位を一元管理
    """
    # 参加情報
    user = models.ForeignKey(User, on_delete=models.CASCADE)    # 参加者
    year = models.IntegerField()                                # 対象年
    month = models.IntegerField()                               # 対象月
    joined_at = models.DateTimeField(auto_now_add=True)        # 参加日時
    
    # リーダーボード情報
    total_hours = models.DecimalField(                         # 総労働時間
        max_digits=6, decimal_places=2, default=0
    )
    rank = models.IntegerField(null=True, blank=True)          # 順位
    last_updated = models.DateTimeField(auto_now=True)         # 最終更新日時
    
    # キャッシュフィールド（パフォーマンス向上用）
    cached_daily_hours = models.JSONField(                     # 日別労働時間キャッシュ
        default=dict, blank=True,
        help_text="{'1': 8.5, '2': 7.0, ...} 形式で保存"
    )
    
    class Meta:
        unique_together = ('user', 'year', 'month')
        ordering = ['rank', '-total_hours']
        indexes = [
            models.Index(fields=['user', 'year', 'month']),
        ]
```

### 3.3 API設計

#### 3.3.1 リーダーボード表示
```
GET /leaderboard/
- 当月のリーダーボード一覧を取得
- 参加者のみアクセス可能
```

#### 3.3.2 リーダーボード参加
```
POST /leaderboard/join/
- 当月のリーダーボードに参加申請
- 10日まで受付
```

#### 3.3.3 参加状況確認
```
GET /leaderboard/status/
- 自分の参加状況と統計を取得
```

#### 3.3.4 リーダーボード更新（内部API）
```
POST /leaderboard/update/
- 労働時間更新時に呼び出し
- timeclockアプリから連携
```

### 3.4 UI設計

#### 3.4.1 リーダーボード一覧画面
```html
<!-- メイン画面構成 -->
<div class="leaderboard-container">
    <div class="leaderboard-header">
        <h1>{{ year }}年{{ month }}月 労働時間リーダーボード</h1>
        <div class="stats">
            <span>参加者: {{ participant_count }}名</span>
            <span>更新: {{ last_updated }}</span>
        </div>
    </div>
    
    <div class="leaderboard-list">
        <!-- リーダーボードテーブル -->
        <table class="leaderboard-table">
            <thead>
                <tr>
                    <th>順位</th>
                    <th>氏名</th>
                    <th>労働時間</th>
                    <th>前日比</th>
                </tr>
            </thead>
            <tbody>
                <!-- リーダーボードアイテム -->
            </tbody>
        </table>
    </div>
    
    <div class="my-stats">
        <!-- 自分の成績 -->
    </div>
</div>
```

#### 3.4.2 参加申請画面
```html
<div class="join-leaderboard">
    <h2>リーダーボード参加申請</h2>
    <div class="notice">
        <p>※ 参加申請は毎月10日まで受け付けています</p>
        <p>※ 参加後のキャンセルはできません</p>
    </div>
    
    <form method="post">
        <button type="submit" class="btn-join">
            {{ year }}年{{ month }}月のリーダーボードに参加する
        </button>
    </form>
</div>
```

## 4. バッチ処理設計

### 4.1 日次リーダーボード更新処理

#### 4.1.1 処理概要
```python
# management/commands/update_leaderboard.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        # 1. 当月の参加者を取得
        # 2. 各参加者の労働時間を再計算
        # 3. リーダーボードを更新
        # 4. 異常値チェック
        # 5. 通知処理
```

#### 4.1.2 処理フロー
1. **データ取得**: 当月参加者リスト
2. **労働時間計算**: TimeClock データから集計
3. **リーダーボード計算**: 総労働時間でソート
4. **データ更新**: LeaderboardEntry テーブル更新
5. **ログ出力**: 処理結果の記録

#### 4.1.3 cron設定
```yaml
# render.yaml に追加
- type: cron
  name: update-daily-leaderboard
  env: python
  buildCommand: pip install -r requirements.txt
  schedule: "0 1 * * *"  # 毎日AM1:00実行
  startCommand: python manage.py update_leaderboard
```

## 5. 連携設計

### 5.1 timeclockアプリとの連携

#### 5.1.1 退勤時の連携
```python
# timeclock/views.py の clock_out 処理に追加
def clock_out(request):
    # 既存の退勤処理
    # ...
    
    # リーダーボード更新処理
    from leaderboard.services import update_user_leaderboard
    try:
        update_user_leaderboard(request.user, timezone.now().date())
    except Exception as e:
        logger.error(f"Ranking update failed: {e}")
    
    return response
```

#### 5.1.2 労働時間計算ロジック
```python
# leaderboard/services.py
def calculate_monthly_working_hours(user, year, month):
    """指定月のユーザー総労働時間を計算"""
    from timeclock.models import TimeClock
    from datetime import datetime
    from decimal import Decimal
    
    # 対象月の開始日と終了日
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    # TimeClockレコードを取得
    records = TimeClock.objects.filter(
        user=user,
        timestamp__gte=start_date,
        timestamp__lt=end_date
    ).order_by('timestamp')
    
    total_hours = Decimal('0')
    daily_hours = {}  # キャッシュ用の日別データ
    clock_in_time = None
    
    for record in records:
        if record.clock_type == 'clock_in':
            clock_in_time = record.timestamp
        elif record.clock_type == 'clock_out' and clock_in_time:
            working_time = record.timestamp - clock_in_time
            hours = Decimal(working_time.total_seconds()) / 3600
            total_hours += hours
            
            # 日別データに追加（キャッシュ用）
            day = record.timestamp.day
            daily_hours[str(day)] = daily_hours.get(str(day), 0) + float(hours)
            
            clock_in_time = None
    
    return total_hours, daily_hours

def update_user_leaderboard(user, date):
    """ユーザーのリーダーボードを更新（退勤時に呼び出し）"""
    try:
        leaderboard = LeaderboardEntry.objects.get(
            user=user,
            year=date.year,
            month=date.month,
            is_active=True
        )
        
        # 労働時間を再計算
        total_hours, daily_hours = calculate_monthly_working_hours(
            user, date.year, date.month
        )
        
        # リーダーボードレコードを更新
        leaderboard.total_hours = total_hours
        leaderboard.cached_daily_hours = daily_hours
        leaderboard.save()
        
        # 全体のリーダーボード順位を更新
        update_all_ranks(date.year, date.month)
        
    except LeaderboardEntry.DoesNotExist:
        # 参加していない場合は何もしない
        pass
```

## 6. セキュリティ設計

### 6.1 アクセス制御

#### 6.1.1 認証・認可
```python
# leaderboard/decorators.py
def leaderboard_participant_required(view_func):
    """リーダーボード参加者のみアクセス許可"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        current_date = timezone.now().date()
        participation = LeaderboardEntry.objects.filter(
            user=request.user,
            year=current_date.year,
            month=current_date.month,
            is_active=True
        ).first()
        
        if not participation:
            return render(request, 'leaderboard/access_denied.html')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
```

#### 6.1.2 データ保護
- 労働時間データの改ざん防止
- 参加者以外のデータアクセス禁止
- 管理者権限の適切な設定

### 6.2 入力値検証

```python
# leaderboard/forms.py
class LeaderboardJoinForm(forms.Form):
    def clean(self):
        current_date = timezone.now().date()
        if current_date.day > 10:
            raise ValidationError("参加申請期間は毎月10日までです。")
        return self.cleaned_data
```
