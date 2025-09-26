# 🎯 給与スキル管理者画面 実装計画

## A. URL構造・画面種別・ナビゲーション設計

### URL構造とビュー/API分類

```
/salary/admin/
├── dashboard/                    # 📱 ビュー: 管理ダッシュボード [NAV表示]
├── skills/                      # 📱 ビュー: スキル一覧・編集 [NAV表示]
│   ├── create/                  # 📱 ビュー: スキル作成フォーム
│   ├── <id>/edit/               # 📱 ビュー: スキル編集フォーム
│   ├── <id>/holders/            # 📱 ビュー: スキル習得者一覧
│   ├── <id>/delete/             # 🔧 API: スキル削除処理
│   └── api/holder-revoke/       # 🔧 API: 習得スキル取り消し処理
├── grades/                      # 📱 ビュー: 給与グレード管理 [NAV表示]
│   ├── create/                  # 📱 ビュー: グレード作成フォーム
│   ├── <id>/edit/               # 📱 ビュー: グレード編集フォーム
│   ├── <id>/members/            # 📱 ビュー: グレード所属者一覧
│   └── <id>/delete/             # 🔧 API: グレード削除処理
├── user-management/             # 📱 ビュー: ユーザー検索画面 [NAV表示]
│   ├── <user_id>/               # 📱 ビュー: ユーザー詳細管理（統合画面）
│   ├── api/grant-skill/         # 🔧 API: 手動スキル付与処理
│   ├── api/revoke-skill/        # 🔧 API: スキル取り消し処理
│   └── api/change-grade/        # 🔧 API: グレード変更処理
└── applications/                # 📱 ビュー: 申告承認待ち一覧 [NAV表示]
    ├── pending/                 # 📱 ビュー: 承認待ち一覧（redirected from above）
    ├── <id>/review/             # 📱 ビュー: 個別申告審査画面
    ├── api/bulk-approve/        # 🔧 API: 一括承認処理
    ├── api/bulk-reject/         # 🔧 API: 一括却下処理
    ├── api/<id>/approve/        # 🔧 API: 個別承認処理
    └── api/<id>/reject/         # 🔧 API: 個別却下処理
```

### ナビゲーション構成

#### メインナビゲーション（管理者専用メニュー）
```
📊 管理ダッシュボード    → /salary/admin/dashboard/
📝 スキル管理           → /salary/admin/skills/
💰 給与グレード管理     → /salary/admin/grades/
👤 ユーザー管理         → /salary/admin/user-management/
✅ 申告承認 (3)         → /salary/admin/applications/ （承認待ち数表示）
```

### 画面遷移フロー

#### ダッシュボードからの遷移
```
📊 ダッシュボード
├── スキル習得者マップ → 📝 各スキルの習得者一覧 (/skills/<id>/holders/)
├── グレード所属者マップ → 💰 各グレードの所属者一覧 (/grades/<id>/members/)
├── 承認待ち申告数 → ✅ 申告承認画面 (/applications/pending/)
└── 最近の活動ログ → 📊 ダッシュボード内での詳細表示
```

#### スキル管理からの遷移
```
📝 スキル一覧
├── 新しいスキル作成 → 📝 スキル作成フォーム (/skills/create/)
├── スキル編集 → 📝 スキル編集フォーム (/skills/<id>/edit/)
├── 習得者一覧 → 📝 スキル習得者一覧 (/skills/<id>/holders/)
└── 習得者一覧から → 👤 ユーザー詳細管理 (/user-management/<user_id>/)
```

#### 給与グレード管理からの遷移
```
💰 グレード一覧
├── 新しいグレード作成 → 💰 グレード作成フォーム (/grades/create/)
├── グレード編集 → 💰 グレード編集フォーム (/grades/<id>/edit/)
├── 所属者一覧 → 💰 グレード所属者一覧 (/grades/<id>/members/)
└── 所属者一覧から → 👤 ユーザー詳細管理 (/user-management/<user_id>/)
```

#### ユーザー管理からの遷移
```
👤 ユーザー検索
├── ユーザー選択 → 👤 ユーザー詳細管理 (/user-management/<user_id>/)
└── ユーザー詳細管理内では他画面への遷移なし（統合画面として完結）
```

#### 申告承認からの遷移
```
✅ 承認待ち一覧
├── 個別審査 → ✅ 個別申告審査 (/applications/<id>/review/)
├── 審査完了後 → ✅ 承認待ち一覧に戻る
└── ユーザー名クリック → 👤 ユーザー詳細管理 (/user-management/<user_id>/)
```

## B. 画面構成

### 1. 管理ダッシュボード 📊

**統計サマリーカード**
- 総スキル数・カテゴリ別
- 総ユーザー数・グレード分布
- 承認待ち申告数
- 最近の活動ログ

**詳細情報カード (🆕)**
- スキル別習得者マップ
  - 各スキル → 習得者一覧（アバター表示）
- グレード別所属者マップ
  - 各グレード → 所属者一覧（アバター表示）

### 2. スキル一覧・編集画面 📝

**スキル一覧テーブル**
- スキル名・カテゴリ・説明
- 習得者数
- 習得者一覧リンク (🆕)
- 編集・削除ボタン

**スキル習得者一覧画面 (🆕)**
- 習得者リスト（習得日・承認者）
- 習得者検索・フィルタ
- 手動での習得取り消し機能

### 3. 給与グレード設定画面 💰

**グレード一覧**
- グレード名・レベル・時給
- 必要スキル・昇進先表示
- 所属者数
- 所属者一覧リンク (🆕)
- 編集・削除ボタン

**グレード所属者一覧画面 (🆕)**
- 所属者リスト（開始日・変更者）
- 昇進条件達成状況
- 所属者検索・フィルタ

### 4. ユーザー管理画面 👤 (🔄統合版)

**ユーザー選択・検索**
- ユーザー名・所属グレード検索
- ユーザー選択

**選択ユーザーの詳細管理 (統合画面)**
- 基本情報表示
- 現在の給与グレード 🆕
  - グレード変更フォーム
  - 変更履歴表示
  - 昇進条件達成状況
- 習得スキル一覧
  - 習得スキル表示（削除可能）
  - 手動スキル付与フォーム
  - 昇進に必要なスキル表示
- 操作ログ 🆕

### 5. 申告承認画面 ✅

**承認待ち申告一覧**
- ユーザー・スキル・申告日
- 申告理由表示
- 一括承認・却下チェックボックス
- 個別審査リンク

**個別申告審査画面**
- 申告詳細情報
- ユーザーの既存スキル確認
- 承認・却下理由入力
- 処理実行ボタン

## C. 実装の詳細設計

### 1. ダッシュボードのスキル・グレード表示

```python
# views.py
class AdminDashboardView(AdminRequiredMixin, TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # スキル別習得者マップ
        skills_with_holders = Skill.objects.prefetch_related(
            'userskill_set__user'
        ).annotate(
            holders_count=Count('userskill')
        )

        # グレード別所属者マップ  
        grades_with_members = SalaryGrade.objects.prefetch_related(
            'usersalarygrade_set__user'
        ).annotate(
            members_count=Count('usersalarygrade')
        )

        context.update({
            'skills_map': skills_with_holders,
            'grades_map': grades_with_members,
            # ... 他の統計データ
        })
        return context
```

### 2. 統合ユーザー管理画面

```python
class UserManagementDetailView(AdminRequiredMixin, DetailView):
    model = User
    template_name = 'salary/admin/user_management/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_object()

        context.update({
            # 給与グレード情報
            'current_grade': user.current_salary_grade,
            'grade_history': user.salary_history.all()[:10],
            'available_grades': SalaryGrade.objects.all(),

            # スキル情報
            'user_skills': user.userskill_set.select_related('skill'),
            'available_skills': Skill.objects.exclude(
                id__in=user.userskill_set.values_list('skill_id', flat=True)
            ),

            # 昇進条件達成状況
            'promotion_status': self.get_promotion_status(user),
        })
        return context
```

### 3. 簡単な操作ログ

```python
# models.py (🆕)
class AdminActionLog(models.Model):
    """管理者操作ログ"""
    ACTION_CHOICES = [
        ('skill_create', 'スキル作成'),
        ('skill_edit', 'スキル編集'),
        ('skill_grant', 'スキル手動付与'),
        ('skill_revoke', 'スキル取り消し'),
        ('grade_create', 'グレード作成'),
        ('grade_edit', 'グレード編集'),
        ('grade_change', 'ユーザーグレード変更'),
        ('application_approve', '申告承認'),
        ('application_reject', '申告却下'),
    ]

    admin_user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='admin_actions_received',
                                   null=True, blank=True)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
```

## D. テンプレート設計例

### ダッシュボードのスキル・グレードマップ

```html
<!-- dashboard.html -->
<div class="row mb-4">
    <!-- スキル別習得者マップ -->
    <div class="col-lg-6">
        <div class="summary-card">
            <div class="card-header">
                <h5><i class="bi bi-award"></i> スキル習得状況</h5>
            </div>
            <div class="card-body">
                {% for skill in skills_map %}
                <div class="skill-map-item mb-3">
                    <div class="d-flex justify-content-between mb-2">
                        <strong>{{ skill.name }}</strong>
                        <span class="badge bg-primary">{{ skill.holders_count }}人</span>
                    </div>
                    <div class="holders-avatars">
                        {% for holder in skill.userskill_set.all|slice:":5" %}
                        <span class="user-avatar" title="{{ holder.user.name }}">
                            {{ holder.user.name|first }}
                        </span>
                        {% endfor %}
                        {% if skill.holders_count > 5 %}
                        <span class="more-holders">+{{ skill.holders_count|add:"-5" }}</span>
                        {% endif %}
                    </div>
                    <a href="{% url 'salary:admin_skill_holders' skill.id %}" 
                       class="small text-primary">詳細を見る →</a>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <!-- グレード別所属者マップ -->
    <div class="col-lg-6">
        <!-- 同様の構造 -->
    </div>
</div>
```

## E. 実装優先順位

### Phase 1 - 基盤 🏗️

1. ✅ URL設計・ベーステンプレート
2. ✅ 権限制御の実装
3. ✅ 管理ダッシュボード（基本版）
4. ✅ AdminActionLogモデル追加

### Phase 2 - コア機能 ⚡

1. ✅ 申告承認画面（最優先）
2. ✅ スキル一覧・編集 + 習得者一覧
3. ✅ 給与グレード設定 + 所属者一覧
4. ✅ 統合ユーザー管理画面

### Phase 3 - 詳細機能 🚀

1. ✅ ダッシュボードのマップ表示
2. ✅ 操作ログ表示
3. ✅ 一括操作機能

## F. ナビゲーション実装の詳細

### 管理者メニューの表示条件
```python
# テンプレートコンテキスト（base.html等で使用）
def admin_menu_context(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return {}
    
    # 承認待ち申告数を取得
    pending_count = SkillApplication.objects.filter(status='pending').count()
    
    return {
        'show_admin_menu': True,
        'pending_applications_count': pending_count,
        'admin_menu_items': [
            {'name': '管理ダッシュボード', 'icon': 'bi-speedometer2', 'url': 'salary:admin_dashboard'},
            {'name': 'スキル管理', 'icon': 'bi-award', 'url': 'salary:admin_skills'},
            {'name': '給与グレード管理', 'icon': 'bi-cash-stack', 'url': 'salary:admin_grades'},
            {'name': 'ユーザー管理', 'icon': 'bi-people', 'url': 'salary:admin_user_management'},
            {'name': f'申告承認 ({pending_count})', 'icon': 'bi-check-circle', 'url': 'salary:admin_applications', 'badge': pending_count if pending_count > 0 else None},
        ]
    }
```

### パンくずリスト設計
```html
<!-- 各画面でのパンくずリスト例 -->

<!-- スキル編集画面 -->
<nav aria-label="breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="{% url 'salary:admin_dashboard' %}">管理ダッシュボード</a></li>
    <li class="breadcrumb-item"><a href="{% url 'salary:admin_skills' %}">スキル管理</a></li>
    <li class="breadcrumb-item active">{{ skill.name }}の編集</li>
  </ol>
</nav>

<!-- ユーザー詳細管理画面 -->
<nav aria-label="breadcrumb">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="{% url 'salary:admin_dashboard' %}">管理ダッシュボード</a></li>
    <li class="breadcrumb-item"><a href="{% url 'salary:admin_user_management' %}">ユーザー管理</a></li>
    <li class="breadcrumb-item active">{{ user.name }}の管理</li>
  </ol>
</nav>
```

## G. 決定事項の記録

### ✅ 確定した仕様

1. **画面名**: 「ユーザー管理」で決定
2. **ダッシュボードのマップ表示**: **アバター形式**で実装
3. **実装順序**: 申告承認画面から開始
4. **ナビゲーション**: 管理者専用メニューとして5つの主要画面を表示
5. **画面遷移**: 各画面から関連する詳細画面への自然な遷移を提供

### 🎯 実装の技術方針

- **ビュー画面**: Djangoテンプレートベースの通常のページ
- **API**: JSON APIとしてAJAX処理用（削除、承認、変更等の操作）
- **権限制御**: `is_staff` または `is_superuser` での制御
- **ナビゲーション**: Bootstrap 5ベースのレスポンシブデザイン

---

## H. API実装詳細計画 🔧

### Phase 4: API機能実装

#### **スキル管理系API**

##### 1. スキル削除API (`AdminSkillDeleteAPI`)
```python
URL: /salary/admin/skills/<id>/delete/
Method: POST
権限: AdminRequiredMixin + @admin_required_api
処理:
  1. スキル存在確認
  2. 習得者がいる場合はUserSkillレコード削除
  3. スキル本体を削除
  4. AdminActionLog記録
  5. JSON応答返却
```

##### 2. スキル習得取消API (`AdminRevokeSkillAPI`)
```python
URL: /salary/admin/skills/api/holder-revoke/
Method: POST
Body: {"user_id": int, "skill_id": int}
権限: AdminRequiredMixin + @admin_required_api
処理:
  1. UserSkillレコード削除
  2. 関連するSkillApplicationのステータスを'revoked'に変更
  3. AdminActionLog記録
  4. ユーザーダッシュボードで「未習得」表示になるよう対応
```

#### **グレード管理系API**

##### 3. グレード削除API (`AdminGradeDeleteAPI`)
```python
URL: /salary/admin/grades/<id>/delete/
Method: POST
権限: AdminRequiredMixin + @admin_required_api
処理:
  1. グレード存在確認
  2. 所属者チェック → いる場合はエラー返却（削除不可）
  3. 所属者がいない場合のみ削除実行
  4. AdminActionLog記録
```

#### **ユーザー管理系API**

##### 4. スキル手動付与API (`AdminGrantSkillAPI`)
```python
URL: /salary/admin/user-management/api/grant-skill/
Method: POST
Body: {"user_id": int, "skill_id": int}
権限: AdminRequiredMixin + @admin_required_api
処理:
  1. 重複付与チェック
  2. UserSkillレコード作成
  3. SkillApplication作成（手動付与用）
  4. AdminActionLog記録
```

##### 5. ユーザースキル取消API (`AdminRevokeUserSkillAPI`)
```python
URL: /salary/admin/user-management/api/revoke-skill/
Method: POST
Body: {"user_skill_id": int}
権限: AdminRequiredMixin + @admin_required_api
処理:
  1. UserSkillレコード削除
  2. 関連SkillApplicationステータス更新
  3. AdminActionLog記録
```

##### 6. グレード変更API (`AdminChangeGradeAPI`)
```python
URL: /salary/admin/user-management/api/change-grade/
Method: POST
Body: {"user_id": int, "grade_id": int}
権限: AdminRequiredMixin + @admin_required_api
処理:
  1. 現在のUserSalaryGrade終了処理
  2. 新しいUserSalaryGrade作成
  3. User.current_salary_grade更新
  4. AdminActionLog記録
```

### **重要な実装方針**

#### **スキル取消時の動作仕様**
- **UserSkill削除**: 習得記録を削除
- **SkillApplication更新**: status='revoked'に変更
- **ダッシュボード表示**: 「未習得」になる

#### **グレード削除時の制限**
- 所属者がいる場合は削除不可
- エラーメッセージで理由説明
- 削除前に所属者数チェック必須

#### **エラーハンドリング**
- 全APIでtry-catch実装
- 適切なエラーメッセージ返却
- ログ記録（成功・失敗両方）

#### **権限とログ**
- 全API操作でAdminActionLog記録
- 操作者・対象ユーザー・操作内容を記録
- APIアクセス権限チェック

### **実装順序**
1. スキル削除API + グレード削除API（基本機能）
2. スキル習得取消API（ユーザーダッシュボード連携考慮）
3. ユーザー管理系API（スキル付与・取消・グレード変更）
4. 全体統合テスト

---

**🚀 実装開始準備完了**  
この設計に基づいて実装を開始します。