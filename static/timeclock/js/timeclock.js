let timeOffset = null;
let isSyncing = false;

function syncWithServerTime() {
    if (isSyncing) return;
    isSyncing = true;
    
    const currentTimeUrl = document.getElementById('currentTimeUrl')?.value;
    if (!currentTimeUrl) {
        isSyncing = false;
        return;
    }
    
    fetch(currentTimeUrl)
        .then(response => response.json())
        .then(data => {
            const serverDateTime = new Date(data.datetime.replace(' ', 'T') + '+09:00');
            const clientTime = new Date();
            
            timeOffset = serverDateTime.getTime() - clientTime.getTime();
            console.log('時刻同期完了: オフセット', Math.round(timeOffset / 1000), '秒');
        })
        .catch(error => {
            console.error('サーバー時刻の取得に失敗:', error);
            timeOffset = 0;
        })
        .finally(() => {
            isSyncing = false;
        });
}

function updateClock() {
    if (timeOffset === null && !isSyncing) {
        syncWithServerTime();
    }
    
    const now = timeOffset !== null 
        ? new Date(Date.now() + timeOffset)
        : new Date();
    
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('digitalClock').textContent = `${hours}:${minutes}:${seconds}`;

    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    document.getElementById('dateDisplay').textContent = `${year}年${month}月${day}日`;
}

function confirmClockAction(event, actionType, actionName) {
    event.preventDefault();
    
    const now = timeOffset !== null 
        ? new Date(Date.now() + timeOffset)
        : new Date();
    const timeString = now.toLocaleTimeString('ja-JP');
    const message = `${actionName}を打刻しますか？\n\n現在時刻: ${timeString}`;
    
    if (confirm(message)) {
        event.target.closest('form').submit();
    }
}

// 共通ユーティリティでanimateProgressBar()を使用

document.addEventListener('DOMContentLoaded', function () {
    syncWithServerTime();
    
    updateClock();
    setInterval(updateClock, 1000);
    
    setInterval(syncWithServerTime, 5 * 60 * 1000);
    
    // 進捗バーのアニメーションを開始
    animateProgressBar();
    
    const clockButtons = document.querySelectorAll('.clock-btn');
    clockButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            const form = button.closest('form');
            const actionType = form.querySelector('input[name="action_type"]').value;
            
            const actionNames = {
                'clock_in': '出勤',
                'clock_out': '退勤',
                'break_start': '休憩開始',
                'break_end': '休憩終了'
            };
            
            confirmClockAction(event, actionType, actionNames[actionType]);
        });
    });
    
    // timeclockから投稿モーダルを開くためのイベントリスナー
    const showPostModalBtn = document.getElementById('showPostModalFromTimeclock');
    if (showPostModalBtn) {
        showPostModalBtn.addEventListener('click', function() {
            const postModal = new bootstrap.Modal(document.getElementById('postModal'));
            postModal.show();
        });
    }
});