# Smart Event Registration — Participant + Committee Portals

## Included
- Public registration page at `/?page=register` (default `/`)
- Password-protected committee dashboard at `/?page=admin`
- SQLite participant database with atomic capacity and waitlist registration
- Gmail SMTP confirmation messages, with QR PNG attachments for confirmed participants
- Waitlist emails and promotion notification after cancellation
- Phone/laptop camera photo QR decoding and manual token check-in
- Duplicate check-in prevention, attendance CSV export, and email delivery log
- Committee-only resend confirmation function

## Local setup (Mac / Windows)
1. Install Python 3.10+ and extract this project.
2. Open Terminal in this folder and run:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   mkdir -p .streamlit
   cp .streamlit_secrets_example.toml .streamlit/secrets.toml
   ```
   On Windows activate with `.venv\\Scripts\\activate` and create/copy files with Explorer.
3. Edit `.streamlit/secrets.toml` with your event details, a strong admin password, Gmail address and **Google App Password** (NOT your normal Gmail password).
4. Start: `streamlit run app.py`
5. Open the participant page at `http://localhost:8501/?page=register` and committee page at `http://localhost:8501/?page=admin`.

## Set up Gmail
1. In the Google account used for sending, turn on **2-Step Verification**.
2. If your account is eligible, create an **App Password** in Google Account settings (search Google Account for "App passwords"). Some accounts do not offer App Passwords; in that case use Gmail API OAuth or a transactional email provider instead.
3. Put the Gmail address in `GMAIL_ADDRESS` and the 16-character App Password (without spaces) in `GMAIL_APP_PASSWORD`.
4. Register with a test email address. Confirm receipt of QR PNG; check committee Email delivery tab for failures.
5. Do not put secrets in source code, share them, or commit `.streamlit/secrets.toml`.

## Important notes
- The QR contains a secret bearer token; treat it as a private ticket.
- The committee portal is protected by a single password stored in Streamlit session state. Use HTTPS when deployed, choose a long unique password, and avoid sharing admin links publicly.
- Camera input captures **photos**, not continuous live scanning. The committee takes a photo and clicks **Confirm camera check-in**. Phone browser camera access generally requires HTTPS (localhost works for development).
- SQLite is fine for a local prototype or single persistent host. **Do not deploy this SQLite version to ephemeral Streamlit Community Cloud storage for a real event**: restarts may lose data. For production use hosted PostgreSQL, managed secrets, proper committee accounts, access controls and backup strategy.
- Emails are attempted immediately after the database commit. Failed sends remain registered and are visible in the admin email log; organizers can resend confirmed tickets. For production-grade delivery guarantees, implement a durable email outbox with retries.
- Registration status and QR ticket are displayed after submission even if sending fails. Waitlisted participants get no usable QR ticket until promoted.
- To avoid unexpected sending limits, note that personal Gmail has sending limits and may temporarily block automated/bulk sending. For large events, use a dedicated transactional provider.
- The cancellation form requires the ticket token. For waitlisted cancellations or missing tickets, contact the committee.
- The event has one capacity and one set of settings. Customize the `EVENT_*` values in secrets.
