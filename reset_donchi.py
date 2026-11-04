"""Explicit local destructive reset: moves the old data folder to ignored backups."""
from __future__ import annotations
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('DONCHI_DATA_DIR',os.environ.get('YEMPRO_DATA_DIR',ROOT/'data'))).resolve()

def main():
    print('DONCHI TOZALASH: do\u02bbkonlar, mahsulotlar, POS savdolar, qarzlar,')
    print('xodimlar, murojaatlar va sessiyalar faol bazadan o\u02bbchiriladi.')
    print('Server to\u02bbxtatilgan bo\u02bblishi shart (Ctrl+C).')
    print('Eski ma\u02bblumotlarning nusxasi backups/ ichiga ko\u02bbchiriladi.')
    print('Faol baza:',DATA)
    try:
        confirmation=input('Rozimisiz? Davom etish uchun TOZALA yozing: ').strip()
    except (EOFError,KeyboardInterrupt):
        return 2
    if confirmation != 'TOZALA':
        print('Bekor qilindi. Hech narsa o\u02bbzgarmadi.')
        return 2
    if DATA.exists():
        target=ROOT/'backups'/('before_reset_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        target.mkdir(parents=True,exist_ok=False)
        try:
            shutil.move(str(DATA),str(target/'data'))
        except Exception as exc:
            print('Ma\u02bblumotlarni ko\u02bbchirishda xato:',exc)
            return 2
        print('Backup:',target/'data')
    else:
        print('Eski data papkasi topilmadi. Toza boshlaymiz.')
    # Import after moving the old data directory, so startup sees a brand-new DB.
    import setup_admin
    return setup_admin.main()

if __name__=='__main__':
    sys.exit(main())
