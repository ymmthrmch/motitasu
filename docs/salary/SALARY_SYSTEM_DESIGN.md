# 給与システム設計書

## 概要
管理者がスキルと給与グレードを設定し、ユーザーの習得スキル状況に応じて給与グレードを管理するシステム。

## 機能要件

### 基本機能
1. **スキル管理**（管理者）
   - スキルの作成・編集・削除
   - スキルカテゴリの設定（技術スキル、接客スキル、管理スキル）
   
2. **給与グレード管理**（管理者）
   - 給与グレードの作成・編集・削除
   - 各グレードに必要な習得スキルの設定
   
3. **ユーザー習得スキル管理**（管理者）
   - ユーザー申告の承認・却下
   - 習得スキル付与・剥奪
   - 習得スキル習得日の記録
   
4. **ユーザー表示機能**
   - 習得済みスキル一覧
   - 次グレードに必要な習得スキル表示
   - 習得スキル保有者の閲覧

5. **ユーザー申告機能**
   - 習得スキル習得の申告
   - 申告状況の確認

## ✅ 確定設計事項

### 1. データモデル設計


### 2. 給与グレード決定ロジック

**✅ 確定事項:**
- **全習得スキル必須**: グレードアップには必要な習得スキルを100%習得が必要
- **手動承認**: 管理者が明示的に給与グレードを変更（自動昇格なし）
- **降格**: 管理者判断により可能

### 3. 時給への反映タイミング

**✅ 確定事項:**
- **既存システム置き換え**: `User.hourly_wage`は完全に廃止
- **必須給与グレード**: UserSalaryGradeが存在しない場合はエラー（給与グレード未設定は許可しない）

### 4. プライバシー設定

**✅ 確定事項:**
- **名前表示**: 習得スキル保有者は実名で表示（例：「田中さん、佐藤さんが習得済み」）

### 5. 承認プロセス

**✅ 確定事項:**
1. ユーザーが習得スキル習得を申告
2. 管理者が申告を承認・却下
3. 承認されたら UserSkill に記録
4. 管理者が給与グレード変更を別途手動で実行

### 6. UI/UX設計

#### 管理者画面
- スキル一覧・編集画面
- 給与グレード設定画面
- ユーザー習得スキル管理画面
- 習得スキル申告承認画面

#### ユーザー画面（ダッシュボード）
```
現在の給与グレード: 一般スタッフ（時給1,200円）

【習得済みスキル】
✅ 基本接客  ✅ レジ操作

【次グレード（主任）に必要なスキル】
❌ チーム管理（習得者: 田中さん、佐藤さん）
❌ 売上分析（習得者: 田中さん）
✅ 基本接客（習得済み）

【習得スキル申告】
- 申告中: データ分析（承認待ち）
- 申告可能なスキル一覧...
```

## ✅ 追加確定事項

### 7. ユーザー給与グレード管理
- **履歴テーブル**: UserSalaryGradeモデルで給与グレード変更履歴を管理
- **現在グレード**: 最新レコードから現在の給与グレードを取得
- **昇格・降格履歴**: 全ての変更履歴を保持

### 8. 習得スキル申告ポリシー
- **重複申告許可**: 同じスキルの再申告可能（却下後の再チャレンジ対応）
- **申告履歴**: 承認・却下の履歴はSkillApplicationで管理

### 9. 削除ポリシー
- **スキル削除**: `on_delete=models.CASCADE` → 関連UserSkillも自動削除
- **給与グレード削除**: `on_delete=models.PROTECT` → ユーザーが紐づいている場合削除不可

### 10. 更新データモデル

#### Userモデル（既存拡張）
```python
# accounts/models.py に追加
class User(AbstractUser):
    @property
    def current_salary_grade(self):
        """現在の給与グレード（最新のUserSalaryGradeから取得）"""
        latest_grade = self.salary_history.order_by('-effective_date').first()
        return latest_grade.salary_grade if latest_grade else None
    
    @property
    def current_hourly_wage(self):
        """現在の時給（給与グレードから取得、必須）"""
        current_grade = self.current_salary_grade
        if current_grade:
            return current_grade.hourly_wage
        raise ValueError(f"ユーザー {self.name} の給与グレードが設定されていません")
```

#### 最終データモデル構成
```python
# salary/models.py

class Skill(models.Model):
    CATEGORY_CHOICES = [
        ('technical', '技術スキル'),
        ('customer_service', '接客スキル'),
        ('management', '管理スキル'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='スキル名')
    description = models.TextField(verbose_name='説明')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='スキルカテゴリ')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class SalaryGrade(models.Model):
    name = models.CharField(max_length=50, verbose_name='グレード名')
    hourly_wage = models.DecimalField(max_digits=6, decimal_places=0, verbose_name='時給')
    level = models.IntegerField(verbose_name='レベル')  # unique=False: 同レベルに複数グレード可能
    required_skills = models.ManyToManyField(Skill, blank=True, verbose_name='必要習得スキル')
    next_possible_grades = models.ManyToManyField('self', blank=True, symmetrical=False, verbose_name='次に昇進可能なグレード')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['level', 'name']

class UserSkill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)  # CASCADE: スキル削除時に習得記録も削除
    acquired_date = models.DateField(verbose_name='習得日')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_skills', verbose_name='承認者')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'skill']

class SkillApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', '承認待ち'),
        ('approved', '承認済み'),
        ('rejected', '却下'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='ステータス')
    application_date = models.DateTimeField(auto_now_add=True, verbose_name='申告日')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_applications', verbose_name='処理者')
    processed_date = models.DateTimeField(null=True, blank=True, verbose_name='処理日')
    comment = models.TextField(blank=True, verbose_name='申告理由・処理コメント')

class UserSalaryGrade(models.Model):
    """ユーザーの給与グレード履歴"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='salary_history')
    salary_grade = models.ForeignKey(SalaryGrade, on_delete=models.PROTECT)
    effective_date = models.DateField(verbose_name='適用日')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='salary_changes_made', verbose_name='変更者')
    reason = models.TextField(blank=True, verbose_name='変更理由')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-effective_date']
        indexes = [
            models.Index(fields=['user', '-effective_date']),
        ]
```

### 11. 複数昇進ルート対応

**✅ 確定事項:**
- **levelフィールド**: 同一レベルに複数の給与グレード配置可能
- **柔軟な昇進ルート**: 異なるスキル組み合わせで同レベルに到達可能

#### 昇進ルート例
```
レベル1: 新人（時給1000円）
├─ 必要スキル: なし

レベル2: 専門スタッフ（時給1200円）
├─ ホールスタッフ
│   └─ 必要スキル: 基本接客、レジ操作
└─ キッチンスタッフ  
    └─ 必要スキル: 基本調理、食材管理

レベル3: リーダー（時給1500円）
├─ ホールリーダー
│   └─ 必要スキル: 基本接客、レジ操作、チーム管理、顧客対応
└─ キッチンリーダー
    └─ 必要スキル: 基本調理、食材管理、チーム管理、メニュー開発

レベル4: マネージャー（時給1800円）
└─ 店舗マネージャー
    └─ 必要スキル: チーム管理、売上分析、人事管理、店舗運営
```

#### ダッシュボード表示例
```
現在の給与グレード: ホールスタッフ（レベル2、時給1,200円）

【習得済みスキル】
✅ 基本接客 [クリックで詳細]  ✅ レジ操作 [クリックで詳細]

【次の選択肢】
🎯 ホールリーダー（折り畳みにする）
  ❌ チーム管理 [クリックで詳細] 
  ❌ 顧客対応 [クリックで詳細]
  ✅ 基本接客（習得済み）
  ✅ レジ操作（習得済み）

🎯 キッチンリーダー（折り畳みにする）
  ❌ 基本調理 [クリックで詳細]
  ❌ 食材管理 [クリックで詳細]  
  ❌ チーム管理 [クリックで詳細]
  ❌ メニュー開発 [クリックで詳細]
```

#### スキル詳細モーダル
```
【スキル詳細】
スキル名: チーム管理
カテゴリ: 管理スキル

説明:
チームメンバーのシフト調整、業務指導、パフォーマンス管理を行うスキル。
リーダーシップを発揮してチーム全体の生産性向上を図る。

【習得者一覧】
✅ 田中 一郎さん（2024/01/15 習得）
✅ 佐藤 花子さん（2024/03/20 習得）

[習得を申告する] ボタン
```

### 12. UI/UX追加仕様

**✅ 確定事項:**
- **スキルクリック**: スキル名をクリックで詳細モーダル表示
- **モーダル内容**: スキル説明、習得者一覧、申告ボタン
- **習得者表示**: 実名と習得日を表示
- **申告ボタン**: 未習得スキルの場合のみ表示

## 実装準備完了

すべての設計が確定しました。**複数昇進ルート対応**も含めて、**フェーズ1（基本モデル・管理画面）**の実装を開始できます！