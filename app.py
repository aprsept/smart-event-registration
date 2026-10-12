"""Two-portal event registration and check-in app."""
import io
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import qrcode
import streamlit as st


def setting(key, default=None):
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except (FileNotFoundError, KeyError):
        return os.getenv(key, default)


EVENT_NAME = setting('EVENT_NAME', 'Business Analytics Workshop')
EVENT_DATE = setting('EVENT_DATE', 'November 14, 2026 · 10:00 AM')
EVENT_VENUE = setting('EVENT_VENUE', 'New York City')
CAPACITY = max(1, int(setting('EVENT_CAPACITY', '100')))
DB_PATH = setting('EVENT_DB_PATH', 'event.db')
ADMIN_PASSWORD = setting('ADMIN_PASSWORD', '')
GMAIL_ADDRESS = setting('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = setting('GMAIL_APP_PASSWORD', '')

st.set_page_config(page_title=EVENT_NAME, page_icon='🎟️', layout='wide')
st.markdown('''<style>
.stApp {background: #f6f8fc;}
h1,h2,h3 {color:#132744;}
[data-testid="stMetric"] {background:white; padding:14px; border-radius:12px; border:1px solid #e2e8f0;}
div.stButton > button[kind="primary"] {background:#255edb; border-radius:10px;}
</style>''', unsafe_allow_html=True)


def connection():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=20000')
    return con


def init_db():
    with connection() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            participant_type TEXT NOT NULL, token TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK(status IN ('confirmed','waitlisted','cancelled')),
            registered_at TEXT NOT NULL, checked_in_at TEXT)''')
        con.execute('''CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL, email_type TEXT NOT NULL,
            outcome TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL)''')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def counts():
    with connection() as con:
        return {r['status']: r['n'] for r in con.execute('SELECT status, COUNT(*) n FROM participants GROUP BY status')}


def register(name, email, kind):
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM participants WHERE email=?', (email,)).fetchone():
            return None, 'This email is already registered. Contact the committee for assistance.'
        n = con.execute("SELECT COUNT(*) FROM participants WHERE status='confirmed'").fetchone()[0]
        status = 'confirmed' if n < CAPACITY else 'waitlisted'
        token = secrets.token_urlsafe(32)
        cursor = con.execute('''INSERT INTO participants
            (name,email,participant_type,token,status,registered_at)
            VALUES (?,?,?,?,?,?)''', (name, email, kind, token, status, now()))
        return dict(id=cursor.lastrowid, name=name, email=email, status=status, token=token), None


def ticket_png(token):
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def send_email(person, email_type):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        error = 'Gmail credentials not configured'
        log_email(person['id'], email_type, 'failed', error)
        return False, error
    confirmed = email_type in ('confirmed', 'promoted', 'resend')
    subject = f"{'Registration confirmed' if confirmed else 'Waitlist confirmation'} — {EVENT_NAME}"
    greeting = f"Hello {person['name']},\n\n"
    if confirmed:
        body = (f"Your registration for {EVENT_NAME} is CONFIRMED.\n"
                f"Date: {EVENT_DATE}\nVenue: {EVENT_VENUE}\n\n"
                "Your personal QR ticket is attached. Please show it at the entrance. "
                "Do not share this ticket.\n\nSee you there!\nEvent Committee")
    else:
        body = (f"You are on the WAITLIST for {EVENT_NAME}.\n"
                f"Date: {EVENT_DATE}\nVenue: {EVENT_VENUE}\n\n"
                "If a seat becomes available, we will email your QR ticket.\n\nEvent Committee")
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = person['email']
    msg.set_content(greeting + body)
    if confirmed:
        msg.add_attachment(ticket_png(person['token']), maintype='image', subtype='png', filename='event-qr-ticket.png')
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=20) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        log_email(person['id'], email_type, 'sent', '')
        return True, ''
    except (smtplib.SMTPException, OSError) as exc:
        error = f'{type(exc).__name__}: {exc}'
        log_email(person['id'], email_type, 'failed', error[:500])
        return False, error


def log_email(pid, kind, outcome, detail):
    with connection() as con:
        con.execute('INSERT INTO email_log(participant_id,email_type,outcome,detail,created_at) VALUES(?,?,?,?,?)',
                    (pid, kind, outcome, detail, now()))


def cancel(token):
    promoted = None
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        p = con.execute('SELECT * FROM participants WHERE token=?', (token,)).fetchone()
        if not p or p['status'] == 'cancelled':
            return 'Ticket not found or already cancelled.', None
        if p['checked_in_at']:
            return 'Already checked in; contact the committee to cancel.', None
        con.execute("UPDATE participants SET status='cancelled' WHERE id=?", (p['id'],))
        if p['status'] == 'confirmed':
            nxt = con.execute("SELECT * FROM participants WHERE status='waitlisted' ORDER BY registered_at,id LIMIT 1").fetchone()
            if nxt:
                con.execute("UPDATE participants SET status='confirmed' WHERE id=?", (nxt['id'],))
                promoted = dict(nxt)
    return 'Registration cancelled.', promoted


def check_in(token):
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        p = con.execute('SELECT * FROM participants WHERE token=?', (token.strip(),)).fetchone()
        if not p:
            return False, 'Invalid QR ticket.'
        if p['status'] != 'confirmed':
            return False, f"Cannot check in {p['name']}: {p['status']}."
        if p['checked_in_at']:
            return False, f"Already checked in: {p['name']} at {p['checked_in_at']}."
        con.execute('UPDATE participants SET checked_in_at=? WHERE id=?', (now(), p['id']))
        return True, f"Check-in successful: {p['name']}."


def decode_camera(upload):
    raw = np.frombuffer(upload.getvalue(), dtype=np.uint8)
    frame = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if frame is None:
        return None
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(frame)
    return data or None


def show_message(ok, message):
    (st.success if ok else st.error)(message)


init_db()
page = st.query_params.get('page', 'register')
if page not in ('register', 'admin'):
    page = 'register'

if page == 'register':
    st.caption('EVENT REGISTRATION PORTAL')
    st.title(f'🎟️ {EVENT_NAME}')
    st.write(f'📅 {EVENT_DATE}  ·  📍 {EVENT_VENUE}')
    status_counts = counts()
    confirmed = status_counts.get('confirmed', 0)
    st.progress(min(confirmed / CAPACITY, 1.0), text=f'{confirmed}/{CAPACITY} confirmed seats')
    st.info(f'{max(0, CAPACITY-confirmed)} seats available. If full, you will join the waitlist.')
    with st.form('registration'):
        name = st.text_input('Full name', max_chars=120)
        email = st.text_input('Email address', max_chars=254)
        kind = st.selectbox('Participant category', ['Student', 'Professional', 'Guest'])
        submitted = st.form_submit_button('Register for event', type='primary')
    if submitted:
        name, email = name.strip(), email.strip().lower()
        if not name or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            st.error('Please enter your name and a valid email address.')
        else:
            result, error = register(name, email, kind)
            if error:
                st.warning(error)
            else:
                st.session_state['latest_ticket'] = result
                sent, _ = send_email(result, result['status'])
                st.success(f"Registration {result['status']}!")
                if sent:
                    st.success('Confirmation email sent. Check your inbox and spam folder.')
                else:
                    st.warning('Registration saved, but email delivery failed. Please contact the committee.')
    if st.session_state.get('latest_ticket'):
        person = st.session_state['latest_ticket']
        st.subheader('Your registration')
        st.write(f"Status: **{person['status'].title()}**")
        if person['status'] == 'confirmed':
            st.image(ticket_png(person['token']), width=220)
            st.download_button('Download your QR ticket', ticket_png(person['token']),
                               file_name='event-ticket.png', mime='image/png')
        st.caption('Keep your ticket private. You may close this page after saving your ticket.')
    with st.expander('Cancel registration using ticket token'):
        st.caption('Contact the committee if you no longer have your token.')
        cancel_token = st.text_input('Ticket token', type='password')
        if st.button('Cancel registration') and cancel_token:
            message, promoted = cancel(cancel_token.strip())
            st.info(message)
            if promoted:
                sent, _ = send_email(promoted, 'promoted')
                if not sent:
                    st.warning('Waitlisted participant promoted, but their confirmation email failed. Committee follow-up required.')
            st.session_state.pop('latest_ticket', None)

else:
    st.caption('COMMITTEE PORTAL · RESTRICTED ACCESS')
    st.title('🛡️ Organizer dashboard')
    if not ADMIN_PASSWORD:
        st.error('ADMIN_PASSWORD is not configured. Set it before using the committee portal.')
        st.stop()
    if not st.session_state.get('admin_authenticated', False):
        with st.form('admin_login'):
            password = st.text_input('Committee password', type='password')
            login = st.form_submit_button('Sign in', type='primary')
        if login:
            if secrets.compare_digest(password, ADMIN_PASSWORD):
                st.session_state['admin_authenticated'] = True
                st.rerun()
            else:
                st.error('Incorrect password.')
        st.stop()
    if st.button('Sign out'):
        st.session_state['admin_authenticated'] = False
        st.rerun()
    with connection() as con:
        df = pd.read_sql_query('SELECT id,name,email,participant_type,status,registered_at,checked_in_at FROM participants ORDER BY id', con)
        logs = pd.read_sql_query('SELECT id,participant_id,email_type,outcome,detail,created_at FROM email_log ORDER BY id DESC LIMIT 200', con)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Total registrations', len(df))
    c2.metric('Confirmed', int((df.status == 'confirmed').sum()) if not df.empty else 0)
    c3.metric('Checked in', int(df.checked_in_at.notna().sum()) if not df.empty else 0)
    c4.metric('Waitlisted', int((df.status == 'waitlisted').sum()) if not df.empty else 0)
    tab_scan, tab_people, tab_email = st.tabs(['📷 Check-in', '👥 Participants', '✉️ Email delivery'])
    with tab_scan:
        st.write('Use your phone or laptop camera to capture a participant QR ticket.')
        photo = st.camera_input('Scan ticket QR code')
        decoded = decode_camera(photo) if photo else None
        if photo and not decoded:
            st.warning('No readable QR code found. Try moving closer or improving lighting.')
        if decoded:
            st.info('QR code detected. Confirm check-in below.')
            if st.button('Confirm camera check-in', type='primary'):
                ok, message = check_in(decoded)
                show_message(ok, message)
        st.divider()
        manual_token = st.text_input('Or enter ticket token manually')
        if st.button('Check in manually', type='primary') and manual_token.strip():
            ok, message = check_in(manual_token)
            show_message(ok, message)
    with tab_people:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button('Export attendance CSV', df.to_csv(index=False).encode('utf-8'),
                           'event-attendance.csv', mime='text/csv')
        st.caption('To resend a ticket, select a confirmed participant ID below.')
        if not df.empty:
            pid = st.selectbox('Participant ID', df.id.tolist(), format_func=lambda x: f"{x} — {df.loc[df.id == x, 'name'].iloc[0]}")
            if st.button('Resend confirmation email'):
                with connection() as con:
                    p = con.execute('SELECT * FROM participants WHERE id=?', (int(pid),)).fetchone()
                if p['status'] != 'confirmed':
                    st.error('Only confirmed participants can receive a QR ticket.')
                else:
                    sent, error = send_email(dict(p), 'resend')
                    show_message(sent, 'Email sent successfully.' if sent else f'Email failed: {error}')
    with tab_email:
        st.dataframe(logs, use_container_width=True, hide_index=True)
        if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
            st.warning('Gmail is not configured. Add credentials to Streamlit secrets.')
