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


EVENT_NAME = setting('EVENT_NAME', 'Indonesia Unplugged 2.0')
EVENT_DATE = setting('EVENT_DATE', 'November 20, 2026')
EVENT_VENUE = setting('EVENT_VENUE', 'Lerner Hall, Columbia University')
CAPACITY = max(1, int(setting('EVENT_CAPACITY', '300')))
INDONESIAN_CAPACITY = int(setting('INDONESIAN_CAPACITY', '120'))
NON_INDONESIAN_CAPACITY = int(setting('NON_INDONESIAN_CAPACITY', '180'))
SEGMENT_CAPACITY = {
    'Indonesian': INDONESIAN_CAPACITY,
    'Non-Indonesian': NON_INDONESIAN_CAPACITY,
}
if min(SEGMENT_CAPACITY.values()) < 0 or sum(SEGMENT_CAPACITY.values()) != CAPACITY:
    st.error('Registration quota configuration is invalid: category capacities must be nonnegative and add up to the total capacity.')
    st.stop()
COUNTRIES = [
    'Afghanistan',
    'Albania',
    'Algeria',
    'American Samoa',
    'Andorra',
    'Angola',
    'Anguilla',
    'Antarctica',
    'Antigua and Barbuda',
    'Argentina',
    'Armenia',
    'Aruba',
    'Australia',
    'Austria',
    'Azerbaijan',
    'Bahamas',
    'Bahrain',
    'Bangladesh',
    'Barbados',
    'Belarus',
    'Belgium',
    'Belize',
    'Benin',
    'Bermuda',
    'Bhutan',
    'Bolivia',
    'Bonaire, Sint Eustatius and Saba',
    'Bosnia and Herzegovina',
    'Botswana',
    'Bouvet Island',
    'Brazil',
    'British Indian Ocean Territory',
    'Brunei',
    'Bulgaria',
    'Burkina Faso',
    'Burundi',
    'Cabo Verde',
    'Cambodia',
    'Cameroon',
    'Canada',
    'Cayman Islands',
    'Central African Republic',
    'Chad',
    'Chile',
    'China',
    'Christmas Island',
    'Cocos (Keeling) Islands',
    'Colombia',
    'Comoros',
    'Congo',
    'Cook Islands',
    'Costa Rica',
    'Croatia',
    'Cuba',
    'Curaçao',
    'Cyprus',
    'Czechia',
    "Côte d'Ivoire",
    'Democratic Republic of the Congo',
    'Denmark',
    'Djibouti',
    'Dominica',
    'Dominican Republic',
    'Ecuador',
    'Egypt',
    'El Salvador',
    'Equatorial Guinea',
    'Eritrea',
    'Estonia',
    'Eswatini',
    'Ethiopia',
    'Falkland Islands (Malvinas)',
    'Faroe Islands',
    'Fiji',
    'Finland',
    'France',
    'French Guiana',
    'French Polynesia',
    'French Southern Territories',
    'Gabon',
    'Gambia',
    'Georgia',
    'Germany',
    'Ghana',
    'Gibraltar',
    'Greece',
    'Greenland',
    'Grenada',
    'Guadeloupe',
    'Guam',
    'Guatemala',
    'Guernsey',
    'Guinea',
    'Guinea-Bissau',
    'Guyana',
    'Haiti',
    'Heard Island and McDonald Islands',
    'Holy See (Vatican City State)',
    'Honduras',
    'Hong Kong',
    'Hungary',
    'Iceland',
    'India',
    'Indonesia',
    'Iran',
    'Iraq',
    'Ireland',
    'Isle of Man',
    'Israel',
    'Italy',
    'Jamaica',
    'Japan',
    'Jersey',
    'Jordan',
    'Kazakhstan',
    'Kenya',
    'Kiribati',
    'Kosovo',
    'Kuwait',
    'Kyrgyzstan',
    'Laos',
    'Latvia',
    'Lebanon',
    'Lesotho',
    'Liberia',
    'Libya',
    'Liechtenstein',
    'Lithuania',
    'Luxembourg',
    'Macao',
    'Madagascar',
    'Malawi',
    'Malaysia',
    'Maldives',
    'Mali',
    'Malta',
    'Marshall Islands',
    'Martinique',
    'Mauritania',
    'Mauritius',
    'Mayotte',
    'Mexico',
    'Micronesia, Federated States of',
    'Moldova',
    'Monaco',
    'Mongolia',
    'Montenegro',
    'Montserrat',
    'Morocco',
    'Mozambique',
    'Myanmar',
    'Namibia',
    'Nauru',
    'Nepal',
    'Netherlands',
    'New Caledonia',
    'New Zealand',
    'Nicaragua',
    'Niger',
    'Nigeria',
    'Niue',
    'Norfolk Island',
    'North Korea',
    'North Macedonia',
    'Northern Mariana Islands',
    'Norway',
    'Oman',
    'Pakistan',
    'Palau',
    'Palestine',
    'Panama',
    'Papua New Guinea',
    'Paraguay',
    'Peru',
    'Philippines',
    'Pitcairn',
    'Poland',
    'Portugal',
    'Puerto Rico',
    'Qatar',
    'Romania',
    'Russia',
    'Rwanda',
    'Réunion',
    'Saint Barthélemy',
    'Saint Helena, Ascension and Tristan da Cunha',
    'Saint Kitts and Nevis',
    'Saint Lucia',
    'Saint Martin (French part)',
    'Saint Pierre and Miquelon',
    'Saint Vincent and the Grenadines',
    'Samoa',
    'San Marino',
    'Sao Tome and Principe',
    'Saudi Arabia',
    'Senegal',
    'Serbia',
    'Seychelles',
    'Sierra Leone',
    'Singapore',
    'Sint Maarten (Dutch part)',
    'Slovakia',
    'Slovenia',
    'Solomon Islands',
    'Somalia',
    'South Africa',
    'South Georgia and the South Sandwich Islands',
    'South Korea',
    'South Sudan',
    'Spain',
    'Sri Lanka',
    'Sudan',
    'Suriname',
    'Svalbard and Jan Mayen',
    'Sweden',
    'Switzerland',
    'Syria',
    'Taiwan',
    'Tajikistan',
    'Tanzania',
    'Thailand',
    'Timor-Leste',
    'Togo',
    'Tokelau',
    'Tonga',
    'Trinidad and Tobago',
    'Tunisia',
    'Turkey',
    'Turkmenistan',
    'Turks and Caicos Islands',
    'Tuvalu',
    'Uganda',
    'Ukraine',
    'United Arab Emirates',
    'United Kingdom',
    'United States',
    'United States Minor Outlying Islands',
    'Uruguay',
    'Uzbekistan',
    'Vanuatu',
    'Venezuela',
    'Vietnam',
    'Virgin Islands, British',
    'Virgin Islands, U.S.',
    'Wallis and Futuna',
    'Western Sahara',
    'Yemen',
    'Zambia',
    'Zimbabwe',
    'Åland Islands',
]

DB_PATH = setting('EVENT_DB_PATH', 'event.db')
ADMIN_PASSWORD = setting('ADMIN_PASSWORD', '')
GMAIL_ADDRESS = setting('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = setting('GMAIL_APP_PASSWORD', '')

st.set_page_config(page_title=EVENT_NAME, page_icon='🎟️', layout='wide')

st.markdown("""
<style>
/* Light appearance, including dark-mode browsers */
:root {
    color-scheme: light;
}

html, body, .stApp,
[data-testid="stAppViewContainer"] {
    color-scheme: light !important;
    color: #17324D !important;
    background:
        radial-gradient(
            ellipse at 10% 12%,
            rgba(144, 197, 233, 0.38),
            transparent 55%
        ),
        radial-gradient(
            ellipse at 90% 28%,
            rgba(194, 225, 246, 0.48),
            transparent 60%
        ),
        radial-gradient(
            ellipse at 25% 85%,
            rgba(164, 211, 239, 0.28),
            transparent 58%
        ),
        linear-gradient(
            135deg,
            #FFFFFF 0%,
            #EDF7FF 50%,
            #FFFFFF 100%
        ) !important;
}

/* Transparent header */
[data-testid="stHeader"] {
    background: transparent !important;
}

/* Main text */
[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3,
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] label {
    color: #17324D !important;
}

/* Headings */
h1, h2, h3 {
    font-family: Georgia, serif !important;
    letter-spacing: -0.5px;
}

h1 {
    font-size: 2.7rem !important;
    font-weight: 700 !important;
}

/* Registration form */
[data-testid="stForm"] {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid #D2E5F3;
    border-radius: 20px;
    padding: 25px;
    box-shadow: 0 8px 30px rgba(60, 110, 150, 0.08);
}

/* Input fields */
[data-testid="stTextInput"] input {
    background: #FFFFFF !important;
    color: #17324D !important;
    border: 1px solid #BCD6E8 !important;
    border-radius: 10px !important;
}

[data-testid="stTextInput"] input::placeholder {
    color: #607D92 !important;
}

/* Buttons */
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button[kind="primary"] {
    background: #397DAA !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
}

div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button[kind="primary"]:hover {
    background: #245C83 !important;
    color: #FFFFFF !important;
}

/* Metrics and dashboard */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.9);
    padding: 16px;
    border-radius: 14px;
    border: 1px solid #D2E5F3;
}

/* Mobile responsiveness */
@media (max-width: 768px) {
    h1 {
        font-size: 2rem !important;
    }

    [data-testid="stForm"] {
        padding: 15px;
    }
}
</style>
""", unsafe_allow_html=True)
  


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
            registered_at TEXT NOT NULL, checked_in_at TEXT, nationality_group TEXT, country TEXT)''')
        # Migrate existing installations without deleting registrations.
        columns = {row['name'] for row in con.execute('PRAGMA table_info(participants)')}
        if 'nationality_group' not in columns:
            con.execute('ALTER TABLE participants ADD COLUMN nationality_group TEXT')
        if 'country' not in columns:
            con.execute('ALTER TABLE participants ADD COLUMN country TEXT')
        con.execute('''CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL, email_type TEXT NOT NULL,
            outcome TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL)''')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def counts():
    with connection() as con:
        return {r['status']: r['n'] for r in con.execute(
            'SELECT status, COUNT(*) n FROM participants GROUP BY status')}


def category_counts():
    with connection() as con:
        rows = con.execute("""SELECT nationality_group, status, COUNT(*) AS n
                              FROM participants
                              GROUP BY nationality_group, status""").fetchall()
    return {(r['nationality_group'], r['status']): r['n'] for r in rows}


def register(name, email, kind, country):
    if country not in COUNTRIES:
        return None, 'Please select a valid country of citizenship.'
    nationality_group = 'Indonesian' if country == 'Indonesia' else 'Non-Indonesian'
    with connection() as con:
        # Lock before counting and inserting so simultaneous signups cannot overbook.
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM participants WHERE email=?', (email,)).fetchone():
            return None, 'This email is already registered. Contact the committee for assistance.'
        confirmed_in_group = con.execute("""SELECT COUNT(*) FROM participants
            WHERE status='confirmed' AND nationality_group=?""",
            (nationality_group,)).fetchone()[0]
        # Legacy registrations without a category are counted against total capacity.
        total_confirmed = con.execute("SELECT COUNT(*) FROM participants WHERE status='confirmed'").fetchone()[0]
        status = ('confirmed' if confirmed_in_group < SEGMENT_CAPACITY[nationality_group]
                  and total_confirmed < CAPACITY else 'waitlisted')
        token = secrets.token_urlsafe(32)
        cursor = con.execute("""INSERT INTO participants
            (name,email,participant_type,token,status,registered_at,nationality_group,country)
            VALUES (?,?,?,?,?,?,?,?)""",
            (name, email, kind, token, status, now(), nationality_group, country))
        return dict(id=cursor.lastrowid, name=name, email=email,
                    status=status, token=token, nationality_group=nationality_group, country=country), None


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
            # Fill the vacated seat only from the same category waitlist.
            # For older records with no category, do not auto-promote someone
            # whose segment allocation is unknown.
            group = p['nationality_group']
            if group in SEGMENT_CAPACITY:
                confirmed_in_group = con.execute("""SELECT COUNT(*) FROM participants
                    WHERE status='confirmed' AND nationality_group=?""", (group,)).fetchone()[0]
                total_confirmed = con.execute("SELECT COUNT(*) FROM participants WHERE status='confirmed'").fetchone()[0]
                if confirmed_in_group < SEGMENT_CAPACITY[group] and total_confirmed < CAPACITY:
                    nxt = con.execute("""SELECT * FROM participants
                        WHERE status='waitlisted' AND nationality_group=?
                        ORDER BY registered_at,id LIMIT 1""", (group,)).fetchone()
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

    st.markdown("""
    ### Experience Indonesia Beyond the Ordinary
    
    Join us for **Indonesia Unplugged 2.0**, a celebration
    of Indonesian culture, community, and connection.
    
    We look forward to welcoming you!
    
    Please complete the registration form below
    to reserve your spot.
    """)
    st.write(f'📅 {EVENT_DATE}  ·  📍 {EVENT_VENUE}')
    # Public page: do not reveal nationality-specific quotas or seat counts.
    # The database still enforces both category limits on submission.
    status_counts = counts()
    confirmed = status_counts.get('confirmed', 0)
    group_counts = category_counts()
    accepting_confirmations = confirmed < CAPACITY and any(
        group_counts.get((group, 'confirmed'), 0) < limit
        for group, limit in SEGMENT_CAPACITY.items()
    )
    st.subheader('Registration')
    if accepting_confirmations:
        st.success('Registration is open.')
    else:
        st.info('Registration is currently accepting waitlist requests.')
    st.caption(
        'Spaces are limited. Registration is subject to availability and event allocation '
        'guidelines. Your confirmation or waitlist status will be sent by email.'
    )
    with st.form('registration'):
        name = st.text_input('Full name', max_chars=120)
        email = st.text_input('Email address', max_chars=254)
        country = st.selectbox(
            'Country of citizenship', COUNTRIES,
            index=None, placeholder='Select your country')
        kind = st.selectbox('Participant type', ['Student', 'Professional', 'Guest'])
        submitted = st.form_submit_button('Register for event', type='primary')
    if submitted:
        name, email = name.strip(), email.strip().lower()
        if not name or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            st.error('Please enter your name and a valid email address.')
        elif country not in COUNTRIES:
            st.error('Please select your country of citizenship.')
        else:
            result, error = register(name, email, kind, country)
            if error:
                st.warning(error)
            else:
                st.session_state['latest_ticket'] = result
                sent, _ = send_email(result, result['status'])
                st.success('Your registration is confirmed!' if result['status'] == 'confirmed'
                           else 'Your registration has been added to the waitlist.')
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
        df = pd.read_sql_query('SELECT id,name,email,country,nationality_group,participant_type,status,registered_at,checked_in_at FROM participants ORDER BY id', con)
        logs = pd.read_sql_query('SELECT id,participant_id,email_type,outcome,detail,created_at FROM email_log ORDER BY id DESC LIMIT 200', con)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Total registrations', len(df))
    c2.metric('Confirmed', int((df.status == 'confirmed').sum()) if not df.empty else 0)
    c3.metric('Checked in', int(df.checked_in_at.notna().sum()) if not df.empty else 0)
    c4.metric('Waitlisted', int((df.status == 'waitlisted').sum()) if not df.empty else 0)
    st.subheader('Confirmed participants by nationality category')
    for group, limit in SEGMENT_CAPACITY.items():
        n = int(((df.nationality_group == group) & (df.status == 'confirmed')).sum()) if not df.empty else 0
        w = int(((df.nationality_group == group) & (df.status == 'waitlisted')).sum()) if not df.empty else 0
        st.write(f'**{group}:** {n}/{limit} confirmed · {w} waitlisted')
        if limit:
            st.progress(min(n / limit, 1.0))
    legacy = int(((df.nationality_group.isna()) & (df.status == 'confirmed')).sum()) if not df.empty else 0
    if legacy:
        st.warning(f'{legacy} existing confirmed registrations have no nationality category. '
                   'They count toward the overall 300-person limit; assign their categories '
                   'before relying on category quotas.')
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
