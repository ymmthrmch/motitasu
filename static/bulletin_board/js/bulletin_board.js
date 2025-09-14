// 伝言板JavaScript機能
document.addEventListener('DOMContentLoaded', function() {
    initializeReactionButtons();
    initializePinButtons();
    initializeMessageForm();
});

// リアクションボタンの初期化
function initializeReactionButtons() {
    document.querySelectorAll('.reaction-btn').forEach(button => {
        // ツールチップを設定
        button.setAttribute('title', 'クリック：リアクション切り替え、長押し：ユーザー一覧表示');
        
        // クリックイベント（リアクション切り替え）
        button.addEventListener('click', function(e) {
            // 長押し後のクリックイベントは無視
            if (this.wasLongPressed) {
                this.wasLongPressed = false;
                e.preventDefault();
                e.stopPropagation();
                return;
            }
            
            if (this.disabled) return;
            
            const messageId = this.closest('.reaction-area').dataset.messageId;
            const reactionType = this.dataset.reactionType;
            
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
                    this.classList.remove('loading');
                    this.disabled = false;
                });
        });
        
        // 長押しイベント（ユーザー一覧表示）
        addLongPressListener(button, function(e) {
            // 長押しフラグを設定
            this.wasLongPressed = true;
            
            const messageId = this.closest('.reaction-area').dataset.messageId;
            const reactionType = this.dataset.reactionType;
            
            // リアクション数を確認
            const countSpan = this.querySelector('.reaction-count');
            const count = parseInt(countSpan.textContent);
            
            if (count === 0) {
                showError('まだリアクションしたユーザーはいません');
                return;
            }
            
            // ユーザー一覧を表示
            showReactionUsers(messageId, reactionType);
        }, 500);
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
    
    // カウント数を更新
    countSpan.textContent = data.reaction_count;
    
    // カウントが0の場合は非表示、1以上の場合は表示
    if (data.reaction_count === 0) {
        countSpan.style.display = 'none';
    } else {
        countSpan.style.display = 'inline';  // 再表示
    }
    
    // ボタンのスタイル更新
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
    const modalTitle = document.getElementById('reactionUsersModalLabel');
    const usersList = document.getElementById('reactionUsersList');
    
    // モーダルタイトルを設定
    modalTitle.textContent = `${data.emoji} リアクションしたユーザー (${data.users.length}人)`;
    
    // ユーザーリストを生成
    if (data.users.length === 0) {
        usersList.innerHTML = '<p class="text-muted text-center">まだリアクションしたユーザーはいません。</p>';
    } else {
        usersList.innerHTML = data.users.map(user => 
            `<div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                <strong>${escapeHtml(user.name)}</strong>
                <small class="text-muted">${user.created_at}</small>
            </div>`
        ).join('');
    }
    
    // Bootstrap Modalを表示
    const modal = new bootstrap.Modal(document.getElementById('reactionUsersModal'));
    modal.show();
}