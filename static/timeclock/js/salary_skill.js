/**
 * 給与・スキル管理用JavaScript（関数型アプローチ）
 */

// DOMContentLoaded時の初期化
document.addEventListener('DOMContentLoaded', function() {
    initializeSalarySkillFeatures();
});

/**
 * 給与スキル機能の初期化
 */
function initializeSalarySkillFeatures() {
    setupSkillDetailButtons();
}

/**
 * スキル詳細ボタンのイベントリスナー設定
 */
function setupSkillDetailButtons() {
    const skillDetailButtons = document.querySelectorAll('.skill-detail-btn');
    skillDetailButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            const skillId = this.dataset.skillId;
            loadSkillDetail(skillId);
        });
    });
}

/**
 * スキル詳細の読み込み
 * @param {string} skillId - スキルID
 */
function loadSkillDetail(skillId) {
    // APIを呼び出し
    fetch(`/salary/skill-detail/${skillId}/`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            displaySkillDetail(data);
        })
        .catch(error => {
            console.error('スキル詳細読み込みエラー:', error);
            showError('スキル詳細の読み込みに失敗しました。');
        });
}

/**
 * スキル詳細表示
 * @param {Object} data - APIから取得したスキル詳細データ
 */
async function displaySkillDetail(data) {
    try {
        // 状態に応じたフォームHTML生成
        let actionForm = '';
        let holdersHtml = '';
        
        // 習得者一覧HTML生成
        if (data.holders.length > 0) {
            holdersHtml = '<div class="row">' + 
                data.holders.map(holder => `
                    <div class="col-md-6 mb-2">
                        <div class="d-flex align-items-center p-2 bg-light rounded">
                            <i class="bi bi-person-circle text-success ms-2 me-3"></i>
                            <div>
                                <div class="fw-semibold">${escapeHtml(holder.user.name)}</div>
                                <small class="text-muted">${holder.acquired_date}</small>
                            </div>
                        </div>
                    </div>
                `).join('') + '</div>';
        } else {
            holdersHtml = `
                <div class="text-center py-3 text-muted bg-light rounded">
                    <i class="bi bi-info-circle mb-2 d-block fs-4"></i>
                    <small>まだ習得者がいません</small>
                </div>`;
        }
        
        // スキルの状態に基づいてフォーム生成
        if (data.is_acquired) {
            // 習得済み状態
            actionForm = `
                <h6 class="skill-section-title text-muted mb-3">
                    <i class="bi bi-check-circle-fill me-2 text-success"></i>習得状況
                </h6>
                <div class="acquisition-status">
                    <div class="status-indicator status-success text-center">
                        <i class="bi bi-check-circle-fill"></i>
                        習得済み
                    </div>
                    <p class="text-muted text-center mt-2 mb-0">
                        習得日: ${data.acquired_date}
                    </p>
                </div>`;
        } else if (data.is_pending) {
            // 申告中状態
            actionForm = `
                <h6 class="skill-section-title text-muted mb-3">
                    <i class="bi bi-hourglass-split me-2 text-warning"></i>申告状況
                </h6>
                <div class="application-status">
                    <div class="status-indicator status-warning text-center">
                        <i class="bi bi-hourglass-split"></i>
                        申告中 - 承認をお待ちください
                    </div>
                    <p class="text-muted text-center mt-2 mb-0">
                        申告日: ${data.application_date}
                    </p>
                </div>`;
        } else if (data.can_apply) {
            // 申告可能状態
            actionForm = `
                <h6 class="skill-section-title text-muted mb-3">
                    <i class="bi bi-plus-circle me-2"></i>スキル習得申告
                </h6>
                <div class="application-form">
                    <div class="mb-3">
                        <label class="form-label">コメント（任意）</label>
                        <textarea id="applicationComment" class="modal-textarea" placeholder="習得の経験や詳細があれば入力してください..." maxlength="200" rows="3"></textarea>
                        <div class="modal-char-counter" id="commentCharCounter">0/200文字</div>
                    </div>
                    <div class="text-center">
                        <button type="button" class="modal-submit-btn" onclick="applyForSkill('${data.skill.id}')">
                            <i class="bi bi-plus-circle"></i> 習得を申告する
                        </button>
                    </div>
                </div>`;
        } else {
            // 申告不可状態（条件未達成など）
            actionForm = `
                <h6 class="skill-section-title text-muted mb-3">
                    <i class="bi bi-info-circle me-2"></i>申告状況
                </h6>
                <div class="text-center py-3 text-muted">
                    <i class="bi bi-lock mb-2 d-block fs-4"></i>
                    <small>申告条件を満たしていません</small>
                </div>`;
        }
        
        // テンプレートファイルを読み込んでモーダル表示
        await showModalFromFile('/static/templates/skill-detail-modal.html', {
            skill_name: data.skill.name,
            skill_category: data.skill.category,
            skill_description: data.skill.description,
            skill_id: data.skill.id,
            holders_count: data.holders.length,
            holders_html: holdersHtml,
            action_form: actionForm
        });
        
        // 文字数カウンター初期化（申告フォームがある場合）
        if (data.can_apply) {
            const textarea = document.getElementById('applicationComment');
            const counter = document.getElementById('commentCharCounter');
            if (textarea && counter) {
                textarea.addEventListener('input', () => {
                    updateCharacterCounter(textarea, counter, null, 200);
                });
            }
        }
        
    } catch (error) {
        console.error('スキル詳細表示エラー:', error);
        showError('スキル詳細の表示に失敗しました。');
    }
}

/**
 * スキル習得申告
 * @param {number} skillId - スキルID
 */
function applyForSkill(skillId) {
    const comment = document.getElementById('applicationComment')?.value || '';
    
    // 確認ダイアログ
    if (!confirm('このスキルの習得を申告しますか？')) {
        return;
    }
    
    // 申告ボタンを無効化
    const applyButton = event.target;
    applyButton.disabled = true;
    applyButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>申告中...';
    
    // API呼び出し
    fetch('/salary/apply-skill/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            skill_id: skillId,
            comment: comment
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 成功時の処理
            showSuccess(data.message);
            // モーダルを閉じる
            setTimeout(() => {
                const modals = document.querySelectorAll('.modal.show');
                modals.forEach(modal => {
                    const bsModal = bootstrap.Modal.getInstance(modal);
                    if (bsModal) bsModal.hide();
                });
                // ページをリロードして最新状態を反映
                window.location.reload();
            }, 2000);
        } else {
            // エラー時の処理
            showError(data.error || 'エラーが発生しました');
            applyButton.disabled = false;
            applyButton.innerHTML = '<i class="bi bi-plus-circle"></i> 習得を申告する';
        }
    })
    .catch(error => {
        console.error('スキル申告エラー:', error);
        showError('申告に失敗しました。再度お試しください。');
        applyButton.disabled = false;
        applyButton.innerHTML = '<i class="bi bi-plus-circle"></i> 習得を申告する';
    });
}

