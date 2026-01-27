@echo off
curl.exe -L "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" -o static\vendor\bootstrap\css\bootstrap.min.css
curl.exe -L "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js" -o static\vendor\bootstrap\js\bootstrap.bundle.min.js
curl.exe -L "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" -o static\vendor\bootstrap-icons\css\bootstrap-icons.css
curl.exe -L "https://cdn.jsdelivr.net/npm/chart.js" -o static\vendor\chartjs\chart.min.js
curl.exe -L "https://cdn.socket.io/4.6.0/socket.io.min.js" -o static\vendor\socketio\socket.io.min.js
curl.exe -L "https://cdn.jsdelivr.net/npm/sweetalert2@11" -o static\vendor\sweetalert2\sweetalert2.all.min.js
curl.exe -L "https://unpkg.com/html5-qrcode" -o static\vendor\html5-qrcode\html5-qrcode.min.js
curl.exe -L "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" -o static\webfonts\inter.css

echo All primary files downloaded.
