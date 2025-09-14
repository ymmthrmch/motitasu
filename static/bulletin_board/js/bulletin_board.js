// 伝言板JavaScript機能

document.addEventListener('DOMContentLoaded', function() {
    initializeReactionButtons();
    initializePinButtons();
    initializeReactionUsersList();
    initializeMessageForm();
});

// リアクションボタンの初期化
function initializeReactionButtons() {
    document.querySelectorAll('.reaction-btn').forEach(button => {
        button.addEventListener('click', function() {
            if (this.disabled) return;
            
            const messageId = this.closest('.reaction-area').dataset.messageId;
            const reactionType = this.dataset.reactionType;
            
            // ボタンをローディング状態に
            this.classList.add('loading');
            this.disabled = true;
            
            toggleReaction(messageId, reactionType)
                .then(data => {
                    if (data.success) {
                        updateReactionButton(this, data);
                    } else {
                        showError('リアクションの処理中にエラーが発生しました: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Reaction error:', error);
                    showError('通信エラーが発生しました');
                })
                .finally(() => {
                    // ローディング状態を解除
                    this.classList.remove('loading');
                    this.disabled = false;
                });
        });
    });
}

// ピン留めボタンの初期化
function initializePinButtons() {
    // ピン留めボタン
    document.querySelectorAll('.pin-btn').forEach(button => {
        button.addEventListener('click', function() {
            const messageId = this.closest('.pin-controls').dataset.messageId;
            const duration = this.dataset.duration;
            
            // ボタンをローディング状態に
            this.classList.add('loading');
            this.disabled = true;
            
            togglePin(messageId, 'pin', duration)
                .then(data => {
                    if (data.success) {
                        showSuccess('メッセージをピン留めしました');
                        // ページをリロードしてピン留め状態を反映
                        setTimeout(() => location.reload(), 1000);
                    } else {
                        showError('ピン留めの処理中にエラーが発生しました: ' + data.error);
                        this.classList.remove('loading');
                        this.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Pin error:', error);
                    showError('通信エラーが発生しました');
                    this.classList.remove('loading');
                    this.disabled = false;
                });
        });
    });

    // ピン留め解除ボタン
    document.querySelectorAll('.unpin-btn').forEach(button => {
        button.addEventListener('click', function() {
            const messageId = this.closest('.pin-controls').dataset.messageId;
            
            // ボタンをローディング状態に
            this.classList.add('loading');
            this.disabled = true;
            
            togglePin(messageId, 'unpin')
                .then(data => {
                    if (data.success) {
                        showSuccess('ピン留めを解除しました');
                        // ページをリロードしてピン留め状態を反映
                        setTimeout(() => location.reload(), 1000);
                    } else {
                        showError('ピン留め解除の処理中にエラーが発生しました: ' + data.error);
                        this.classList.remove('loading');
                        this.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Unpin error:', error);
                    showError('通信エラーが発生しました');
                    this.classList.remove('loading');
                    this.disabled = false;
                });
        });
    });
}

// リアクションユーザー一覧の初期化
function initializeReactionUsersList() {
    document.querySelectorAll('.reaction-count').forEach(countSpan => {
        countSpan.style.cursor = 'pointer';
        countSpan.setAttribute('title', 'クリックでユーザー一覧を表示');
        countSpan.addEventListener('click', function(e) {
            e.stopPropagation();
            
            const count = parseInt(this.textContent);
            if (count === 0) return;
            
            const reactionBtn = this.closest('.reaction-btn');
            const messageId = reactionBtn.closest('.reaction-area').dataset.messageId;
            const reactionType = reactionBtn.dataset.reactionType;
            
            showReactionUsers(messageId, reactionType);
        });
    });
}

// メッセージフォームの初期化
function initializeMessageForm() {
    const form = document.querySelector('form[method="post"]');
    if (!form) return;
    
    const textarea = form.querySelector('textarea[name="content"]');
    const submitButton = form.querySelector('button[type="submit"]');
    
    if (!textarea || !submitButton) return;
    
    // 文字数カウンター
    const maxLength = textarea.maxLength;
    const counter = document.createElement('small');
    counter.className = 'text-muted';
    counter.textContent = `0/${maxLength}文字`;
    textarea.parentNode.appendChild(counter);
    
    textarea.addEventListener('input', function() {
        const currentLength = this.value.length;
        counter.textContent = `${currentLength}/${maxLength}文字`;
        
        if (currentLength > maxLength * 0.9) {
            counter.className = 'text-warning';
        } else {
            counter.className = 'text-muted';
        }
    });
    
    // フォーム送信時の処理
    form.addEventListener('submit', function() {
        submitButton.classList.add('loading');
        submitButton.disabled = true;
        submitButton.textContent = '投稿中...';
    });
}

// リアクション切り替えAPI呼び出し
async function toggleReaction(messageId, reactionType) {
    const response = await fetch('/bulletin/api/reaction/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCsrfToken()
        },
        body: `message_id=${messageId}&reaction_type=${reactionType}`
    });
    return await response.json();
}

// ピン留め切り替えAPI呼び出し
async function togglePin(messageId, action, duration = null) {
    let body = `message_id=${messageId}&action=${action}`;
    if (duration) {
        body += `&duration=${duration}`;
    }
    
    const response = await fetch('/bulletin/api/pin/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCsrfToken()
        },
        body: body
    });
    return await response.json();
}

// リアクションボタンの表示更新
function updateReactionButton(button, data) {
    const countSpan = button.querySelector('.reaction-count');
    countSpan.textContent = data.reaction_count;
    
    if (data.action === 'added') {
        button.classList.remove('btn-outline-secondary');
        button.classList.add('btn-secondary');
    } else {
        button.classList.remove('btn-secondary');
        button.classList.add('btn-outline-secondary');
    }
}

// リアクションユーザー一覧を表示
async function showReactionUsers(messageId, reactionType) {
    try {
        const url = `/bulletin/api/reaction-users/${messageId}/${reactionType}/`;
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            displayReactionUsersModal(data);
        } else {
            showError('ユーザー一覧の取得中にエラーが発生しました: ' + data.error);
        }
    } catch (error) {
        console.error('Error fetching reaction users:', error);
        showError('通信エラーが発生しました');
    }
}

// リアクションユーザー一覧モーダルを表示
function displayReactionUsersModal(data) {
    const modal = document.getElementById('reactionUsersModal');
    const modalTitle = modal.querySelector('.modal-title');
    const usersList = document.getElementById('reactionUsersList');
    
    modalTitle.textContent = `${data.emoji} リアクションしたユーザー (${data.users.length}人)`;
    
    if (data.users.length === 0) {
        usersList.innerHTML = '<p class="text-muted">まだリアクションしたユーザーはいません。</p>';
    } else {
        usersList.innerHTML = data.users.map(user => 
            `<div class="mb-2 d-flex justify-content-between align-items-center">
                <strong>${escapeHtml(user.name)}</strong>
                <small class="text-muted">${user.created_at}</small>
            </div>`
        ).join('');
    }
    
    // Bootstrap Modal を表示
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// CSRFトークンを取得
function getCsrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

// HTMLエスケープ
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// 成功メッセージを表示
function showSuccess(message) {
    showNotification(message, 'success');
}

// エラーメッセージを表示
function showError(message) {
    showNotification(message, 'error');
}

// 通知を表示
function showNotification(message, type) {
    // 既存の通知があれば削除
    const existingNotification = document.querySelector('.notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    const notification = document.createElement('div');
    notification.className = `notification alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show`;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    
    notification.innerHTML = `
        ${escapeHtml(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // 5秒後に自動で削除
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// 時間経過の表示更新（ピン留めの残り時間など）
function updateTimeDisplays() {
    document.querySelectorAll('[data-expires-at]').forEach(element => {
        const expiresAt = new Date(element.dataset.expiresAt);
        const now = new Date();
        const remaining = expiresAt - now;
        
        if (remaining > 0) {
            const hours = Math.floor(remaining / (1000 * 60 * 60));
            const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
            element.textContent = `${hours}時間${minutes}分後に期限切れ`;
        } else {
            element.textContent = '期限切れ';
            element.classList.add('text-muted');
        }
    });
}

// 1分ごとに時間表示を更新
setInterval(updateTimeDisplays, 60000);

// ページ読み込み時に時間表示を更新
updateTimeDisplays();