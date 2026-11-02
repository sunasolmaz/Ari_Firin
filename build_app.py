# build_app.py
"""
Arı Fırın Muhasebe Uygulaması - Standalone .exe Derleme Script'i
"""

import os
import sys
import subprocess

def main():
    print("=" * 60)
    print("ARI FIRIN - STANDALONE EXE DERLEME BASLATILIYOR")
    print("=" * 60)
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=Arı_Fırın",
        "--add-data=src/ui/assets;src/ui/assets",
        "--exclude-module=torch",
        "--exclude-module=tensorflow",
        "--exclude-module=scipy",
        "--exclude-module=sklearn",
        "--exclude-module=transformers",
        "--exclude-module=cv2",
        "--exclude-module=nltk",
        "--exclude-module=onnxruntime",
        "--exclude-module=fastapi",
        "--exclude-module=django",
        "--exclude-module=IPython",
        "--exclude-module=Cython",
        "--exclude-module=numba",
        "--exclude-module=llvmlite",
        "--exclude-module=bitsandbytes",
        "--exclude-module=boto3",
        "--exclude-module=botocore",
        "--exclude-module=accelerate",
        "--exclude-module=matplotlib",
    ]
    
    if os.path.exists("resources"):
        cmd.append("--add-data=resources;resources")
        
    icon_path = os.path.join("resources", "icons", "app.ico")
    if os.path.exists(icon_path):
        cmd.append(f"--icon={icon_path}")
        
    cmd.append("main.py")
    
    print("Calistirilan Komut:", " ".join(cmd))
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("DERLEME BASARIYLA TAMAMLANDI!")
        print("Dagitim Klasoru: dist/Arı_Fırın/")
        print("Calistirilabilir Dosya: dist/Arı_Fırın/Arı_Fırın.exe")
        print("=" * 60)
    else:
        print("\nDerleme sirasinda bir hata olustu.")

if __name__ == "__main__":
    main()
