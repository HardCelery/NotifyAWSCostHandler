
$SevenZIP = "C:\Program Files\7-zip\7z.exe"

Copy-Item -Path "$PSScriptRoot\src\*.py" ".env\Lib\site-packages"


# 圧縮対象フォルダ指定
$Source = Join-Path $PSScriptRoot ".env\Lib\site-packages"


# 宛先指定
$Pname = Split-Path $PSScriptRoot -Leaf
$Dest = "$Pname.zip"


# zipフォルダが存在したら削除
if (Test-Path $Dest) {
    Remove-Item $Dest -Force
}

# 圧縮実行
& $SevenZIP a -tzip $Dest "$Source\*"
