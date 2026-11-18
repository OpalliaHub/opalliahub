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
                CREATE TABLE IF NOT EXISTS application_history (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  job_id TEXT NOT NULL REFERENCES jobs(id),
                  before_state TEXT NOT NULL, after_state TEXT NOT NULL,
                  applied INTEGER NOT NULL DEFAULT 1 CHECK(applied IN (0,1)));
            ''')
            columns = {row['name'] for row in con.execute('PRAGMA table_info(jobs)')}
            for name in ('expires_at', 'availability', 'last_live_checked'):
                if name not in columns:
                    con.execute('ALTER TABLE jobs ADD COLUMN ' + name + " TEXT NOT NULL DEFAULT ''")

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
            # Reuse IDs of previously imported JobsDB snapshot records so their
            # application foreign keys remain intact when live data replaces them.
            existing = {r['url']: dict(r) for r in con.execute(
                "SELECT id,url,last_live_checked FROM jobs WHERE source LIKE 'JobsDB%'")}
            for job in jobs:
                identity = job['source'] + '|' + (job.get('url') or (job['title'] + '|' + job['company'] + '|' + job.get('location', '')))
                jid = hashlib.sha256(identity.encode()).hexdigest()[:20]
                old = existing.get(job.get('url')) if job['source'].startswith('JobsDB') else None
                if old:
                    jid = old['id']
                    if old['last_live_checked'] and not job.get('last_live_checked'):
                        continue  # A historical import must not downgrade live data.
                row = (jid, job['source'], job['title'], job['company'], job.get('location', ''), job.get('salary', ''),
                       job.get('url', ''), job['description'], json.dumps(job.get('skills', []), ensure_ascii=False),
                       job.get('published_at', ''), now(), int(job.get('is_demo', False)), int(job.get('remote', False)),
                       job.get('expires_at', ''), job.get('availability', ''), job.get('last_live_checked', ''))
                con.execute('''INSERT INTO jobs
                 (id,source,title,company,location,salary,url,description,skills,published_at,collected_at,is_demo,remote,expires_at,availability,last_live_checked)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                 source=excluded.source,title=excluded.title, company=excluded.company, location=excluded.location, salary=excluded.salary,
                 description=excluded.description, skills=excluded.skills, published_at=excluded.published_at,
                 collected_at=excluded.collected_at, remote=excluded.remote, expires_at=excluded.expires_at,
                 availability=excluded.availability,last_live_checked=excluded.last_live_checked''', row)
                if job['source'].startswith('JobsDB'):
                    existing[job.get('url')] = {'id': jid, 'last_live_checked': job.get('last_live_checked', '')}
                count += 1
        return count

    def reserve_jobsdb_attempt(self, stamp):
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute("SELECT value FROM settings WHERE key='jobsdb_last_attempt'").fetchone()
            if row and (datetime.fromisoformat(stamp) - datetime.fromisoformat(json.loads(row[0]))).total_seconds() < 60:
                raise ValueError('JobsDB 更新请求至少间隔 60 秒，请稍后再试。')
            con.execute("INSERT INTO settings VALUES ('jobsdb_last_attempt',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(stamp),))

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
            con.execute('BEGIN IMMEDIATE')
            if not con.execute('SELECT id FROM jobs WHERE id=?', (jid,)).fetchone():
                raise ValueError('岗位不存在。')
            row = con.execute('SELECT status,note,updated_at FROM applications WHERE job_id=?', (jid,)).fetchone()
            before = dict(row) if row else None
            after = None if status == '未收藏' else dict(status=status, note=note[:4000], updated_at=now())
            if (before is None and after is None) or (before and after and
                    (before['status'], before['note']) == (after['status'], after['note'])):
                return  # Saving unchanged content must not erase the redo stack.
            self._restore_application(con, jid, after)
            con.execute('DELETE FROM application_history WHERE applied=0')
            con.execute('INSERT INTO application_history(job_id,before_state,after_state) VALUES(?,?,?)',
                        (jid, json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))
            con.execute('DELETE FROM application_history WHERE id NOT IN '
                        '(SELECT id FROM application_history ORDER BY id DESC LIMIT 50)')

    @staticmethod
    def _restore_application(con, jid, snapshot):
        """Restore an immutable JSON snapshot inside the caller's transaction."""
        if snapshot is None:
            con.execute('DELETE FROM applications WHERE job_id=?', (jid,))
        else:
            con.execute('INSERT INTO applications VALUES (?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET '
                        'status=excluded.status,note=excluded.note,updated_at=excluded.updated_at',
                        (jid, snapshot['status'], snapshot['note'], snapshot['updated_at']))

    def history_status(self):
        with self.connection() as con:
            counts = dict(con.execute('SELECT applied,COUNT(*) FROM application_history GROUP BY applied'))
        return {'undo': counts.get(1, 0), 'redo': counts.get(0, 0)}

    def application_history(self, action):
        """Two persistent LIFO stacks; update and stack transfer are atomic."""
        if action not in ('undo', 'redo'):
            raise ValueError('未知的历史操作。')
        undo = action == 'undo'
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            # Only fixed literals determine SQL order; user text is never SQL.
            row = con.execute('SELECT * FROM application_history WHERE applied=? ORDER BY id ' +
                              ('DESC' if undo else 'ASC') + ' LIMIT 1', (int(undo),)).fetchone()
            if row is None:
                raise ValueError('没有可以撤销的记录。' if undo else '没有可以重做的记录。')
            snapshot = json.loads(row['before_state' if undo else 'after_state'])
            self._restore_application(con, row['job_id'], snapshot)
            con.execute('UPDATE application_history SET applied=? WHERE id=?', (int(not undo), row['id']))
        return self.history_status()

    def log(self, source, status, count, message):
        with self.connection() as con:
            con.execute('INSERT INTO collection_runs(source,status,count,message,created_at) VALUES(?,?,?,?,?)', (source, status, count, message, now()))

    def logs(self):
        with self.connection() as con:
            return [dict(row) for row in con.execute('SELECT * FROM collection_runs ORDER BY id DESC LIMIT 30')]

    def clear_resume(self):
        with self.connection() as con:
            con.execute("DELETE FROM settings WHERE key IN ('resume', 'profile', 'ai_analysis', 'polished')")
