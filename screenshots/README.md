# תצלומי מסך של מסד הנתונים

יש לצרף לתיקייה זו תצלומי מסך (PNG/JPG) של:

1. **מבנה הטבלאות** - למשל פתיחת `payments.db` בכלי כמו [DB Browser for SQLite](https://sqlitebrowser.org/) (חינמי) ולשונית "Database Structure", או הרצת `.schema` בשורת הפקודה של sqlite3.
2. **תוכן `t_data`** - כמה שורות לדוגמה (`SELECT * FROM t_data LIMIT 20;`).
3. **תוכן `t_targil`** - כל 12 הנוסחאות (`SELECT * FROM t_targil;`).
4. **תוכן `t_results` ו-`t_log`** לאחר הרצת השיטות (`SELECT * FROM t_log;`).

## איך לפתוח את `payments.db`

**אופציה 1 - DB Browser for SQLite (GUI, מומלץ לתצלומי מסך נוחים):**
הורדה מ-https://sqlitebrowser.org/dl/ , ואז File → Open Database → לבחור את `payments.db`.

**אופציה 2 - שורת פקודה (sqlite3, אם מותקן):**
```powershell
sqlite3 payments.db
.schema
SELECT * FROM t_data LIMIT 20;
SELECT * FROM t_targil;
SELECT * FROM t_log;
.quit
```

**אופציה 3 - Python (מותקן כבר בפרויקט זה):**
```powershell
python -c "import sqlite3; c=sqlite3.connect('payments.db'); [print(r) for r in c.execute('SELECT * FROM t_targil')]"
```
