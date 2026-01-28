@echo off
curl.exe -L "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/fonts/bootstrap-icons.woff2" -o static\vendor\bootstrap-icons\fonts\bootstrap-icons.woff2
curl.exe -L "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/fonts/bootstrap-icons.woff" -o static\vendor\bootstrap-icons\fonts\bootstrap-icons.woff

curl.exe -L "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuOKfMZg.ttf" -o static\webfonts\Inter-300.ttf
curl.exe -L "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfMZg.ttf" -o static\webfonts\Inter-400.ttf
curl.exe -L "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuI6fMZg.ttf" -o static\webfonts\Inter-500.ttf
curl.exe -L "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf" -o static\webfonts\Inter-600.ttf
curl.exe -L "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuFuYMZg.ttf" -o static\webfonts\Inter-700.ttf

echo Font files downloaded.
