document.addEventListener('DOMContentLoaded', function () {
    // プログレスバーのアニメーション
    animateProgressBar();

    // カレンダーの日付クリックイベント（将来の拡張用）
    const calendarDays = document.querySelectorAll('.calendar-day.has-data');
    calendarDays.forEach(day => {
        day.addEventListener('click', function () {
            // 将来的に日別の詳細表示機能を追加可能
            console.log('Day clicked:', this);
        });
    });

    // カレンダーの月切り替え時のアニメーション
    const calendarCard = document.querySelector('.calendar-card');
    if (calendarCard) {
        calendarCard.style.opacity = '0';
        setTimeout(() => {
            calendarCard.style.transition = 'opacity 0.5s ease';
            calendarCard.style.opacity = '1';
        }, 100);
    }

    // サマリーカードの数値アニメーション
    const statsValues = document.querySelectorAll('.animate-value');
    statsValues.forEach(element => {
        const text = element.textContent;
        const match = text.match(/^(\d+)/);
        if (match) {
            const value = parseInt(match[1]);
            const suffix = text.replace(/^\d+/, '');
            element.dataset.suffix = suffix;
            animateValue(element, 0, value, 1000);
        }
    });

    // ツールチップの初期化（Bootstrap 5.3）
    initializeTooltips();

    // 目標設定モーダルの処理
    initializeTargetModal();
});

// 目標設定モーダルの初期化
function initializeTargetModal() {
    const setTargetBtn = document.getElementById('setTargetBtn');
    const setTargetModal = document.getElementById('setTargetModal');
    const setTargetForm = document.getElementById('setTargetForm');
    const submitBtn = document.getElementById('setTargetSubmitBtn');
    const messageDiv = document.getElementById('targetMessage');

    if (!setTargetBtn || !setTargetModal || !setTargetForm) {
        return; // 要素が存在しない場合は処理を終了
    }

    // モーダル表示ボタンのクリック
    setTargetBtn.addEventListener('click', function() {
        const modal = new bootstrap.Modal(setTargetModal);
        modal.show();
    });

    // フォーム送信処理
    setTargetForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(setTargetForm);
        const targetIncome = formData.get('target_income');
        
        if (!targetIncome || parseInt(targetIncome) <= 0) {
            showTargetMessage('目標月収を正しく入力してください。', 'danger');
            return;
        }

        // 送信中の状態にする
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 設定中...';
        submitBtn.classList.add('disabled');
        showTargetMessage('', '');

        // API呼び出し
        fetch('/timeclock/api/set-monthly-target/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showTargetMessage(data.message, 'success');
                setTimeout(() => {
                    location.reload(); // ページを再読み込みして結果を反映
                }, 1500);
            } else {
                showTargetMessage(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showTargetMessage('エラーが発生しました。再度お試しください。', 'danger');
        })
        .finally(() => {
            // ボタンを元に戻す
            submitBtn.disabled = false;
            submitBtn.classList.remove('disabled');
            submitBtn.innerHTML = '<i class="bi bi-check"></i> 設定する';
        });
    });
}

// メッセージ表示用関数
function showTargetMessage(message, type) {
    const messageDiv = document.getElementById('targetMessage');
    if (!messageDiv) return;

    if (message) {
        messageDiv.className = `small ${type === 'success' ? 'text-success' : type === 'danger' ? 'text-danger' : 'text-muted'}`;
        messageDiv.innerHTML = `<i class="bi bi-${type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-triangle' : 'info-circle'}"></i> ${message}`;
    } else {
        messageDiv.className = '';
        messageDiv.innerHTML = '';
    }
}