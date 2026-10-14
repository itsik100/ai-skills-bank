#!/usr/bin/env python3
"""review-and-sign — בדיקה לפני מסירה.

שימוש:
    python3 check.py output.md source1.md [source2.md ...]
    python3 check.py --clean clean.md

מדווח על:
  1. סלוטים שלא מולאו ({{ }})
  2. באנר חסר ("טיוטה — לא חתומה" או "נחתם ע"י ...")
  3. זמן קריאה (מילים / 200, בלי סעיף "ראיות")
  4. כל מספר בתוצר שלא נמצא באף מקור
  5. מספרים שלא נמצאו במקור וגם לא תויגו — חובה לתקן או לתייג לפני מסירה

מותאם מ-pre-publish-check.md של kill-the-wall-of-text (swan-gtm, MIT).
בדיקות הסגנון באנגלית הושמטו. מספרים חד-ספרתיים, שמות, הישגים בלי מספר
וחיזוק/החלשה של טענות — בודקים בעין.

--clean: בדיקת עותק נקי לשליחה, אחרי חתימה. נכשלת אם נשארו בו תגית,
מספור [N], באנר (טיוטה/חתום/"אושר ללא שינויים"), כותרת "ראיות", בלוק
החתימה, הביטוי "לא במקור" או {{ }}. לא צריך קובצי מקור.

קוד יציאה: 0 = אין ממצא חוסם; 1 = יש ממצא חוסם; 2 = שימוש שגוי.
"""
import math
import re
import sys

BANNER_DRAFT = 'טיוטה — לא חתומה'
BANNER_SIGNED = re.compile(r'נחתם ע["״]י .+, \d{2}/\d{2}/\d{4}')
TAGS = ('[מונח]', '[מחושב]', '[מוצע]', '[לא מאומת]', '[סתירה]', '[לא במקור]')
EVIDENCE = re.compile(r'^.*ראיות.*$', re.M)
URL = re.compile(r'https?://\S+')
# תאריך מלא, או מספר עם פסיקים/נקודה עשרונית, עם יחידה אופציונלית
NUM = re.compile(r'(?<![\w.])(\d{1,2}/\d{1,2}/\d{2,4}|\d[\d,]*(?:\.\d+)?)\s?(%|K\b|M\b|₪)?')
TAG_WINDOW = 60  # תווים אחרי המספר, באותה שורה, שבהם מחפשים תגית


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def core(num):
    """הצורה שמחפשים במקור: בלי פסיקים, בלי יחידה."""
    return num.replace(',', '')


def in_sources(num, unit, sources):
    c = core(num)
    if '/' in c:
        pat = r'(?<![\d/])' + re.escape(c) + r'(?![\d/])'
    else:
        pat = r'(?<![\d.])' + re.escape(c) + r'(?!\d|\.\d)'
        if unit == '%':
            pat += r'\s?%'  # "30%" לא נחשב נמצא בגלל "30 דקות"
    return any(re.search(pat, s) for s in sources)


def tagged(text, end):
    line_end = text.find('\n', end)
    window = text[end:line_end if line_end != -1 else len(text)][:TAG_WINDOW]
    return any(t in window for t in TAGS)


CLEAN_CHECKS = [
    ('תגית', re.compile('|'.join(re.escape(t) for t in TAGS))),
    ('מספור [N]', re.compile(r'\[\d+\]')),
    ('באנר', re.compile(re.escape(BANNER_DRAFT) + r'|נחתם ע["״]י|אושר ללא שינויים')),
    ('כותרת "ראיות"', re.compile(r'^\s*(?:#+|─+|-{2,}|\*\*)?\s*ראיות\b', re.M)),
    ('בלוק חתימה', re.compile(r'קראת הכל ואתה עומד מאחוריו|^\s*─+\s*חתימה', re.M)),
    ('"לא במקור"', re.compile(r'לא במקור')),
    ('סלוט {{ }}', re.compile(r'\{\{.*?\}\}', re.S)),
]


def check_clean(path):
    text = read(path)
    found = 0
    for name, rx in CLEAN_CHECKS:
        for m in rx.finditer(text):
            found += 1
            line = text.count('\n', 0, m.start()) + 1
            print('✗ %s נשאר (שורה %d): %s' % (name, line, m.group(0).strip()[:40]))
    print('\n%s' % ('%d ממצאים — העותק לא נקי. לא למסור.' % found if found else '✓ העותק נקי.'))
    return 1 if found else 0


def main(argv):
    if len(argv) == 3 and argv[1] == '--clean':
        return check_clean(argv[2])
    if len(argv) < 3 or '--clean' in argv:
        print(__doc__.strip().split('\n\n')[1])
        return 2
    out = read(argv[1])
    sources = [read(p).replace(',', '') for p in argv[2:]]
    blocking = 0

    # 1. סלוטים שלא מולאו
    slots = re.findall(r'\{\{.*?\}\}', out, re.S)
    if slots:
        blocking += 1
        print('✗ סלוטים שלא מולאו (%d): %s' % (len(slots), ' · '.join(s[:40] for s in slots)))
    else:
        print('✓ אין סלוטים פתוחים')

    # 2. באנר
    if BANNER_DRAFT in out:
        print('✓ באנר: טיוטה — לא חתומה')
    elif BANNER_SIGNED.search(out):
        print('✓ באנר: חתום')
    else:
        blocking += 1
        print('✗ באנר חסר: "%s"' % BANNER_DRAFT)

    # 3. זמן קריאה — הגוף בלי סעיף "ראיות"
    m = EVIDENCE.search(out)
    body = out[:m.start()] if m else out
    if not m:
        print('! אין סעיף "ראיות"')
    words = len(re.findall(r'\S+', URL.sub('', body)))
    mins = max(1, math.ceil(words / 200))
    note = ' — יותר מ-2 דקות: לחתוך או להעביר ל"ראיות"' if words > 400 else ''
    print('זמן קריאה: %d מילים בגוף ≈ %d דק\'%s' % (words, mins, note))

    # 4–5. מספרים
    # לא נבדקים: קישורים, שורת הבאנר, ומספור פריטים [N]. מחליפים ברווחים כדי לשמור מיקומים
    blank = lambda r: ' ' * len(r.group(0))
    text = URL.sub(blank, out)
    text = BANNER_SIGNED.sub(blank, text)
    text = re.sub(r'^\s*\[\d+\]', blank, text, flags=re.M)
    missing, untagged = [], []
    for nm in NUM.finditer(text):
        num, unit = nm.group(1), nm.group(2) or ''
        if '/' not in num and len(core(num).replace('.', '')) < 2:
            continue  # חד-ספרתי: בודקים בעין
        if in_sources(num, unit, sources):
            continue
        label = num + unit
        if label not in missing:
            missing.append(label)
        if nm.start() < len(body) and not tagged(text, nm.end()):
            line = text.count('\n', 0, nm.start()) + 1
            untagged.append('%s (שורה %d)' % (label, line))

    print('מספרים שלא נמצאו באף מקור (%d): %s' % (len(missing), ' · '.join(missing) or 'אין'))
    if untagged:
        blocking += 1
        print('✗ לא במקור וגם לא מתויגים (%d) — לתקן או לתייג:\n  %s' % (len(untagged), '\n  '.join(untagged)))
    else:
        print('✓ כל מספר שלא במקור מתויג')

    print('\n%s. לבדוק בעין: מספרים חד-ספרתיים, שמות, הישגים בלי מספר, חיזוק או החלשה של טענות.' %
          ('%d ממצאים חוסמים' % blocking if blocking else 'אין ממצאים חוסמים'))
    return 1 if blocking else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv))
