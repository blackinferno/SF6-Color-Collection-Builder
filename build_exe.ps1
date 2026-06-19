python -m PyInstaller `
  --noconfirm `
  --windowed `
  --name "SF6 Color Collection Builder" `
  --icon "img/colormixer.png" `
  --add-data "img;img" `
  app/main.py

Copy-Item `
  -LiteralPath "update_log.txt" `
  -Destination "dist/SF6 Color Collection Builder/update_log.txt" `
  -Force
