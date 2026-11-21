from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3, os
from datetime import datetime, date, timedelta
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'defect_tracker.db')
app = Flask(__name__)
app.secret_key = 'DefectDesk@2026#SecureKey!92'

STATUSES = ['NEW', 'ASSIGNED', 'RESOLVED', 'REOPENED', 'VERIFIED', 'CLOSED']
TRANSITIONS = {
    'NEW': ['ASSIGNED'], 'ASSIGNED': ['RESOLVED'],
    'RESOLVED': ['VERIFIED', 'REOPENED'], 'REOPENED': ['ASSIGNED'],
    'VERIFIED': ['CLOSED'], 'CLOSED': []
}
SEVERITIES = ['Critical', 'High', 'Medium', 'Low']
PRIORITIES = ['P1 - Urgent', 'P2 - High', 'P3 - Normal', 'P4 - Low']


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def init_db():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS defects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, description TEXT NOT NULL,
            component TEXT NOT NULL, severity TEXT NOT NULL,
            priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'NEW',
            assignee TEXT DEFAULT '', resolution TEXT DEFAULT '',
            discovered_on TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            defect_id INTEGER NOT NULL REFERENCES defects(id) ON DELETE CASCADE,
            changed_at TEXT NOT NULL, old_status TEXT, new_status TEXT NOT NULL,
            note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS prevention (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL, category TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0, note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        ''')
        count = con.execute('SELECT COUNT(*) FROM prevention').fetchone()[0]
        if count == 0:
            items = [
                ('Review requirements for ambiguity', 'Requirements'),
                ('Perform design and code reviews', 'Review'),
                ('Run static analysis before testing', 'Code quality'),
                ('Maintain unit tests for changed modules', 'Testing'),
                ('Verify build and deployment configuration', 'Release')]
            con.executemany('INSERT INTO prevention(item,category,created_at) VALUES(?,?,?)',
                            [(a,b,datetime.now().isoformat(timespec='seconds')) for a,b in items])


def now(): return datetime.now().isoformat(timespec='seconds')

@app.route('/')
def dashboard():
    with db() as con:
        defects = con.execute('SELECT * FROM defects ORDER BY id DESC').fetchall()
        total = len(defects)
        counts = Counter(d['status'] for d in defects)
        severity = Counter(d['severity'] for d in defects)
        open_count = sum(counts[s] for s in ['NEW','ASSIGNED','REOPENED'])
        resolved_count = sum(counts[s] for s in ['RESOLVED','VERIFIED','CLOSED'])
        recent = con.execute('SELECT * FROM defects ORDER BY updated_at DESC LIMIT 5').fetchall()
        prevention = con.execute('SELECT COUNT(*) total, SUM(completed) done FROM prevention').fetchone()
    # Simple transparent forecast: linear trend of defects discovered over the last 7 days.
    with db() as con:
        rows = con.execute('SELECT discovered_on, COUNT(*) n FROM defects WHERE discovered_on >= ? GROUP BY discovered_on',
                           ((date.today()-timedelta(days=6)).isoformat(),)).fetchall()
    daily = {r['discovered_on']: r['n'] for r in rows}
    series = [daily.get((date.today()-timedelta(days=6-i)).isoformat(),0) for i in range(7)]
    forecast = max(0, round(sum(series)/7, 1))
    return render_template('dashboard.html', total=total, counts=counts, severity=severity,
        open_count=open_count, resolved_count=resolved_count, recent=recent,
        prevention=prevention, forecast=forecast, series=series, statuses=STATUSES)

@app.route('/defects')
def defects():
    status = request.args.get('status','')
    search = request.args.get('q','').strip()
    sql = 'SELECT * FROM defects WHERE 1=1'; args=[]
    if status: sql += ' AND status=?'; args.append(status)
    if search:
        sql += ' AND (title LIKE ? OR component LIKE ? OR assignee LIKE ?)'
        args += [f'%{search}%']*3
    sql += ' ORDER BY updated_at DESC'
    with db() as con: rows=con.execute(sql,args).fetchall()
    return render_template('defects.html', defects=rows, statuses=STATUSES, selected=status, q=search)

@app.route('/defects/new', methods=['GET','POST'])
def new_defect():
    if request.method == 'POST':
        fields = ['title','description','component','severity','priority','assignee','discovered_on']
        data = {k:request.form.get(k,'').strip() for k in fields}
        if not all(data[k] for k in ['title','description','component','severity','priority','discovered_on']):
            flash('Please fill in all required fields.', 'error')
            return render_template('new_defect.html', data=data, severities=SEVERITIES, priorities=PRIORITIES)
        if data['severity'] not in SEVERITIES or data['priority'] not in PRIORITIES:
            flash('Choose a valid severity and priority.', 'error')
            return render_template('new_defect.html', data=data, severities=SEVERITIES, priorities=PRIORITIES)
        stamp=now()
        with db() as con:
            cur=con.execute('''INSERT INTO defects(title,description,component,severity,priority,assignee,discovered_on,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)''',(data['title'],data['description'],data['component'],data['severity'],data['priority'],data['assignee'],data['discovered_on'],stamp,stamp))
            con.execute('INSERT INTO history(defect_id,changed_at,old_status,new_status,note) VALUES(?,?,?,?,?)',
                        (cur.lastrowid,stamp,None,'NEW','Defect recorded'))
        flash('Defect recorded successfully.', 'success'); return redirect(url_for('defect_detail', defect_id=cur.lastrowid))
    return render_template('new_defect.html', data={'discovered_on':date.today().isoformat()}, severities=SEVERITIES, priorities=PRIORITIES)

@app.route('/defects/<int:defect_id>', methods=['GET','POST'])
def defect_detail(defect_id):
    with db() as con: defect=con.execute('SELECT * FROM defects WHERE id=?',(defect_id,)).fetchone()
    if not defect: return render_template('404.html'),404
    if request.method == 'POST':
        target=request.form.get('status',''); note=request.form.get('note','').strip()
        if target not in TRANSITIONS.get(defect['status'],[]):
            flash(f"Invalid transition: {defect['status']} cannot move to {target}.",'error')
        else:
            stamp=now(); resolution=request.form.get('resolution','').strip()
            with db() as con:
                con.execute('UPDATE defects SET status=?, updated_at=?, resolution=CASE WHEN ? != \'\' THEN ? ELSE resolution END WHERE id=?',
                            (target,stamp,resolution,resolution,defect_id))
                con.execute('INSERT INTO history(defect_id,changed_at,old_status,new_status,note) VALUES(?,?,?,?,?)',
                            (defect_id,stamp,defect['status'],target,note or 'Status updated'))
            flash('Defect status updated.','success')
        return redirect(url_for('defect_detail',defect_id=defect_id))
    with db() as con: history=con.execute('SELECT * FROM history WHERE defect_id=? ORDER BY id DESC',(defect_id,)).fetchall()
    return render_template('detail.html', defect=defect, history=history, next_statuses=TRANSITIONS[defect['status']])

@app.route('/prevention', methods=['GET','POST'])
def prevention():
    with db() as con:
        if request.method=='POST':
            action=request.form.get('action')
            if action=='add':
                item=request.form.get('item','').strip(); category=request.form.get('category','General').strip()
                if item: con.execute('INSERT INTO prevention(item,category,created_at) VALUES(?,?,?)',(item,category,now()))
            elif action=='toggle':
                pid=request.form.get('id'); con.execute('UPDATE prevention SET completed=1-completed WHERE id=?',(pid,))
            elif action=='delete':
                con.execute('DELETE FROM prevention WHERE id=?',(request.form.get('id'),))
            return redirect(url_for('prevention'))
        items=con.execute('SELECT * FROM prevention ORDER BY category,id').fetchall()
    return render_template('prevention.html', items=items)

@app.route('/reports')
def reports():
    with db() as con:
        all_defects=con.execute('SELECT * FROM defects').fetchall()
    statuses={s:sum(d['status']==s for d in all_defects) for s in STATUSES}
    severities={s:sum(d['severity']==s for d in all_defects) for s in SEVERITIES}
    components=Counter(d['component'] for d in all_defects)
    return render_template('reports.html', total=len(all_defects), statuses=statuses, severities=severities, components=components)

@app.route('/api/summary')
def api_summary():
    with db() as con: rows=con.execute('SELECT status, COUNT(*) n FROM defects GROUP BY status').fetchall()
    return jsonify({r['status']:r['n'] for r in rows})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
