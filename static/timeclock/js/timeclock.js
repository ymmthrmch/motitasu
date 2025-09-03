function updateClock() {
    const currentTimeUrl = document.getElementById('currentTimeUrl').value;
    
    fetch(currentTimeUrl)
        .then(response => response.json())
        .then(data => {
            document.getElementById('digitalClock').textContent = data.time;
            document.getElementById('dateDisplay').textContent = data.date;
        })
        .catch(error => {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            document.getElementById('digitalClock').textContent = `${hours}:${minutes}:${seconds}`;
            
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            document.getElementById('dateDisplay').textContent = `${year}年${month}月${day}日`;
        });
}

document.addEventListener('DOMContentLoaded', function() {
    updateClock();
    setInterval(updateClock, 1000);
});