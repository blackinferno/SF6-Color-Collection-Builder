python -m PyInstaller `
  --noconfirm `
  --windowed `
  --name "SF6 Color Collection Builder" `
  --icon "img/colormixer.png" `
  --add-data "img;img" `
  --add-data "Tool/MyCustomCollection/MyCustomCollection.png;Tool/MyCustomCollection" `
  app/main.py
