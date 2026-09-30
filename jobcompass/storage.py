"""SQLite repository with parameterized queries and transactional upserts."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as con:
            con.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
                  company TEXT NOT NULL, location TEXT, salary TEXT, url TEXT,
                  description TEXT NOT NULL, skills TEXT, published_at TEXT,
                  collected_at TEXT NOT NULL, is_demo INTEGER DEFAULT 0, remote INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS applications (
                  job_id TEXT PRIMARY KEY REFERENCES jobs(id), status TEXT NOT NULL,
                  note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS collection_runs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, status TEXT,
                  count INTEGER, message TEXT, created_at TEXT);
            ''')

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            with con:
                yield con
        finally:
            con.close()

    def set(self, key, value):
        with self.connection() as con:
            con.execute('INSERT INTO settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value, ensure_ascii=False)))

    def get(self, key, default=None):
        with self.connection() as con:
            row = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def upsert_jobs(self, jobs):
        count = 0
        with self.connection() as con:
            for job in jobs:
                identity = job['source'] + '|' + (job.get('url') or (job['title'] + '|' + job['company'] + '|' + job.get('location', '')))
                jid = hashlib.sha256(identity.encode()).hexdigest()[:20]
                row = (jid, job['source'], job['title'], job['company'], job.get('location', ''), job.get('salary', ''),
                       job.get('url', ''), job['description'], json.dumps(job.get('skills', []), ensure_ascii=False),
                       job.get('published_at', ''), now(), int(job.get('is_demo', False)), int(job.get('remote', False)))
                con.execute('''INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                 title=excluded.title, company=excluded.company, location=excluded.location, salary=excluded.salary,
                 description=excluded.description, skills=excluded.skills, published_at=excluded.published_at,
                 collected_at=excluded.collected_at, remote=excluded.remote''', row)
                count += 1
        return count

    def jobs(self):
        with self.connection() as con:
            rows = con.execute('''SELECT jobs.*, applications.status, applications.note FROM jobs
             LEFT JOIN applications ON jobs.id=applications.job_id ORDER BY collected_at DESC''').fetchall()
        result = []
        for row in rows:
            job = dict(row)
            job['skills'] = json.loads(job['skills'])
            result.append(job)
        return result

    def application(self, jid, status, note):
        if status not in ('收藏', '已投递', '面试中', '已录用', '已结束', '未收藏'):
            raise ValueError('未知的投递状态。')
        with self.connection() as con:
            if not con.execute('SELECT id FROM jobs WHERE id=?', (jid,)).fetchone():
                raise ValueError('岗位不存在。')
            if status == '未收藏':
                con.execute('DELETE FROM applications WHERE job_id=?', (jid,))
            else:
                con.execute('INSERT INTO applications VALUES (?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated_at=excluded.updated_at', (jid, status, note[:4000], now()))

    def log(self, source, status, count, message):
        with self.connection() as con:
            con.execute('INSERT INTO collection_runs(source,status,count,message,created_at) VALUES(?,?,?,?,?)', (source, status, count, message, now()))

    def logs(self):
        with self.connection() as con:
            return [dict(row) for row in con.execute('SELECT * FROM collection_runs ORDER BY id DESC LIMIT 30')]

    def clear_resume(self):
        with self.connection() as con:
            con.execute("DELETE FROM settings WHERE key IN ('resume', 'profile', 'ai_analysis', 'polished')")
