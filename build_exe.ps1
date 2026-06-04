python -m PyInstaller `
  --noconfirm `
  --windowed `
  --name "SF6 Color Collection Builder" `
  --icon "img/colormixer.png" `
  --add-data "img;img" `
  app/main.py

Copy-Item `
  -LiteralPath "release_notes.txt" `
  -Destination "dist/SF6 Color Collection Builder/release_notes.txt" `
  -Force
