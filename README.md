# Smart Attendance Analyser

**Smarter Attendance. Better Insights.**

A complete attendance management web app: Flask (Python) + SQLite + Bootstrap 5 + Chart.js.
Made for a BCA final-year project demo and viva.

## Features

| Page | What it does |
|------|--------------|
| Login | Admin login, hashed password, session, logout |
| Dashboard | Live totals, Present/Absent today, At-Risk count, doughnut + monthly trend charts, recent records |
| Students | Add / edit / delete / search / view details, attendance % per student |
| Subjects | Add / edit / delete / search / view details |
| Mark Attendance | Pick date + subject, mark Present/Absent, save or update, no duplicates, delete a day's records |
| Analysis | Overall %, student-wise, subject-wise, daily, weekly, monthly, Low / At-Risk / Excellent lists, 4 filters |
| Reports | 6 report types, date + student + subject filters, PDF, CSV, Print |
| Settings | Admin profile, change username, change password, college info, academic year |

### How statuses are decided (useful for viva)

| Attendance % | Status |
|---|---|
| below 75 | **At Risk** |
| 75 to below 85 | **Low** |
| 85 to below 90 | Good |
| 90 and above | **Excellent** |

The 75 and 90 limits can be changed in **Settings > College Information**.
Students with no attendance records yet show "No Data" and are not counted as At Risk.

## Folder structure

```
smart_attendance_analyser/
├── app.py              <- Flask app: routes, database, login, reports
├── analysis.py         <- all percentage / chart / report calculations
├── requirements.txt    <- Python libraries needed
├── Procfile            <- start command (Heroku-style platforms)
├── render.yaml         <- optional one-click setup file for Render
├── README.md
├── .gitignore
├── database/           <- attendance.db is created here automatically
├── templates/          <- all HTML pages (base.html is the shared layout)
└── static/
    ├── css/style.css
    ├── js/script.js
    └── images/logo.svg
```

## Database tables

* `admin` (id, username, password_hash, full_name)
* `students` (id, reg_no UNIQUE, name, email, phone, class_name)
* `subjects` (id, code UNIQUE, name, semester, teacher)
* `attendance` (id, student_id FK, subject_id FK, date, status, **UNIQUE(student_id, subject_id, date)**)
* `settings` (key, value) - college name, academic year, thresholds

Deleting a student or subject also deletes its attendance rows (`ON DELETE CASCADE`).

---

## 1. Run on your computer

**ಕನ್ನಡ:** ಮೊದಲು ಪೈಥಾನ್ ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡಿ (Python 3.10 ಅಥವಾ ಹೆಚ್ಚಿನದು). ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡುವಾಗ **"Add Python to PATH"** ಅನ್ನು ಟಿಕ್ ಮಾಡಲು ಮರೆಯಬೇಡಿ.

1. Install Python from <https://www.python.org/downloads/> (tick **Add Python to PATH**).
2. Extract the ZIP. You will get the folder `smart_attendance_analyser`.
   **ಕನ್ನಡ:** ZIP ಫೈಲ್ ಅನ್ನು Extract ಮಾಡಿ. ಫೋಲ್ಡರ್ ಒಳಗೆ app.py ಇರಬೇಕು.
3. Open a terminal **inside that folder**
   (Windows: open the folder, click the address bar, type `cmd`, press Enter. VS Code: *Terminal > New Terminal*).
4. Create a virtual environment and install the libraries:

   **Windows**
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
   **Mac / Linux**
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   **ಕನ್ನಡ:** ಮೇಲಿನ ಕಮಾಂಡ್‌ಗಳು ಅಗತ್ಯ ಲೈಬ್ರರಿಗಳನ್ನು (Flask, reportlab) ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡುತ್ತವೆ. ಇದನ್ನು ಒಮ್ಮೆ ಮಾತ್ರ ಮಾಡಬೇಕು.

5. (Optional) Add demo students and attendance so the charts look full:
   ```
   flask --app app seed-demo
   ```
   **ಕನ್ನಡ:** ಈ ಕಮಾಂಡ್ ಪ್ರದರ್ಶನಕ್ಕಾಗಿ ಮಾದರಿ (demo) ವಿದ್ಯಾರ್ಥಿಗಳು ಮತ್ತು ಹಾಜರಾತಿ ಸೇರಿಸುತ್ತದೆ. ನಿಮ್ಮ ನಿಜವಾದ ಡೇಟಾ ಬೇಕಾದರೆ ಇದನ್ನು ಬಿಟ್ಟುಬಿಡಿ.

6. Start the app:
   ```
   python app.py
   ```
7. Open <http://127.0.0.1:5000> in your browser.
   **ಕನ್ನಡ:** ಬ್ರೌಸರ್‌ನಲ್ಲಿ http://127.0.0.1:5000 ತೆರೆಯಿರಿ. ನಿಲ್ಲಿಸಲು ಟರ್ಮಿನಲ್‌ನಲ್ಲಿ `Ctrl + C` ಒತ್ತಿ.

The database file `database/attendance.db` is created automatically on first run and keeps your data after restarts.

## 2. Demo login and how to change it

| Username | Password |
|---|---|
| `admin` | `admin123` |

**ಕನ್ನಡ:** ಲಾಗಿನ್ ವಿವರ: ಯೂಸರ್‌ನೇಮ್ `admin`, ಪಾಸ್‌ವರ್ಡ್ `admin123`. ಲಾಗಿನ್ ಆದ ನಂತರ **Settings** ಪುಟದಲ್ಲಿ ಯೂಸರ್‌ನೇಮ್ ಮತ್ತು ಪಾಸ್‌ವರ್ಡ್ ಬದಲಾಯಿಸಿ.

* **Change inside the app:** Settings > *Change Username* / *Change Password*.
* **Forgot the password?** Run `flask --app app reset-admin` to go back to `admin / admin123`.
* **Set a different first password** (before the very first run, or on Render): environment variables
  `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
* The yellow "Demo login" hint on the login page disappears automatically once the default password is changed.

## 3. Test every feature (checklist for your demo)

1. Log in with `admin / admin123`. Wrong password shows an error.
2. **Students** > *Add New Student* > fill the form > Save. Try a duplicate register number (it is rejected). Search, View (eye icon), Edit (pencil), Delete (bin).
3. **Subjects** > *Add Subject* > same tests.
4. **Mark Attendance** > choose today + a subject > tick Absent for someone > *Save Attendance*. Reload the page: your choices are still there and the button now says *Update Attendance*. Saving again never creates duplicates.
5. **Dashboard**: Present Today / Absent Today / At Risk and the charts changed.
6. **Analysis**: use the Student / Subject / Date / Month filters. Check Low, At Risk and Excellent lists.
7. **Reports**: switch report types, apply filters, then *Export CSV*, *Download PDF*, *Print Report*.
8. **Settings**: change the college name and academic year, then check the PDF header and sidebar.
9. **Logout**, then try opening <http://127.0.0.1:5000/students> - it sends you to the login page.

---

## 4. Upload to GitHub

**ಕನ್ನಡ:** GitHub ನಲ್ಲಿ ಹೊಸ Repository ರಚಿಸಿ, ನಂತರ ಕೆಳಗಿನ ಕಮಾಂಡ್‌ಗಳಿಂದ ಕೋಡ್ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.

1. Create a free account at <https://github.com>.
2. Click **New repository** > name it `smart-attendance-analyser` > keep it empty (no README) > **Create**.
3. Install Git from <https://git-scm.com/downloads>, then in the project folder:
   ```
   git init
   git add .
   git commit -m "Smart Attendance Analyser"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/smart-attendance-analyser.git
   git push -u origin main
   ```
   (Replace `YOUR-USERNAME`. GitHub may ask you to sign in in the browser.)

**No Git?** On the empty repository page click **uploading an existing file**, drag in everything *inside* the project folder (not the folder itself), and press **Commit changes**.
Do **not** upload the `venv` folder. The included `.gitignore` already skips it when you use Git.

## 5. Deploy on Render

**ಕನ್ನಡ:** Render.com ನಲ್ಲಿ GitHub ಖಾತೆಯಿಂದ ಲಾಗಿನ್ ಮಾಡಿ → **New → Web Service** → ನಿಮ್ಮ Repository ಆರಿಸಿ → ಕೆಳಗಿನ ಸೆಟ್ಟಿಂಗ್‌ಗಳನ್ನು ಹಾಕಿ.

1. Sign up at <https://render.com> with your GitHub account.
2. **New +** > **Web Service** > pick your `smart-attendance-analyser` repository.
3. Fill in:

   | Setting | Value |
   |---|---|
   | Language / Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn app:app --workers 1 --threads 4 --timeout 60` |
   | Instance Type | Free |

   Render takes the start command from this screen (or from `render.yaml`), so the `Procfile` is just a reference copy.
4. Open **Environment** and add:

   | Key | Value | Why |
   |---|---|---|
   | `SECRET_KEY` | any long random text | keeps login sessions secure |
   | `ADMIN_PASSWORD` | your own password | **do this** - the site is public |
   | `PYTHON_VERSION` | `3.12.7` | fixes the Python version |
   | `SEED_DEMO` | `1` | fills demo data on every start (see warning below) |

5. Click **Create Web Service**. After the build finishes, open the `https://....onrender.com` link and log in.

Alternatively choose **New + > Blueprint** and Render will read `render.yaml` for you (then set `ADMIN_PASSWORD` in the dashboard).

### IMPORTANT: free Render plan does not keep SQLite data

**ಮುಖ್ಯ ಸೂಚನೆ:** ಉಚಿತ Render ಪ್ಲಾನ್‌ನಲ್ಲಿ ಸರ್ವರ್ ರೀಸ್ಟಾರ್ಟ್ ಅಥವಾ 15 ನಿಮಿಷ ನಿಷ್ಕ್ರಿಯವಾದ ನಂತರ SQLite ಡೇಟಾ ಅಳಿದುಹೋಗುತ್ತದೆ. ಆದ್ದರಿಂದ ಡೆಮೊಗೆ `SEED_DEMO=1` ಬಳಸಿ; ಶಾಶ್ವತ ಡೇಟಾ ಬೇಕಾದರೆ ಕಂಪ್ಯೂಟರ್‌ನಲ್ಲಿ ರನ್ ಮಾಡಿ ಅಥವಾ Persistent Disk (ಪಾವತಿ) ಬಳಸಿ.

Render's free web services have an **ephemeral filesystem**: the SQLite file is erased when the service restarts, redeploys, or sleeps after 15 minutes of no traffic (and it takes about a minute to wake up). Passwords changed in Settings are also lost for the same reason, which is why `ADMIN_PASSWORD` should be set as an environment variable. Persistent disks are not available on free web services ([Render docs](https://render.com/docs/free)).

Your options:

* **For a college demo / viva:** keep `SEED_DEMO=1`. Every start gets a fresh, full demo database. Add your own live data during the demo only.
* **For real, permanent data:** run the app locally (data is saved in `database/attendance.db`), or upgrade to a paid instance, add a **Disk** (mount path `/var/data`) and set `DATABASE_PATH=/var/data/attendance.db`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `'python' is not recognized` | Reinstall Python and tick *Add Python to PATH*, or try `py` instead of `python` |
| `No module named flask` | Activate the venv (`venv\Scripts\activate`) and run `pip install -r requirements.txt` |
| Charts / icons missing | Check your internet - Bootstrap and Chart.js load from a CDN |
| Port 5000 busy | `set PORT=5001` (Windows) or `export PORT=5001` (Mac/Linux), then `python app.py` |
| "Request expired" message | Your form session timed out. Go back, refresh and submit again |
| Forgot password | `flask --app app reset-admin` |

## Security features (for viva)

* Passwords stored as salted hashes (`werkzeug.security`), never as plain text.
* Every page except Login needs an active admin session.
* CSRF token on every form that changes data.
* All SQL uses `?` placeholders (protects against SQL injection).
* Server-side form validation, unique constraints and safe redirects after login.
* Foreign keys with cascade delete and `UNIQUE(student_id, subject_id, date)` to stop duplicate attendance.

## Tech stack

Python 3 · Flask · SQLite · HTML5 · CSS3 · JavaScript · Bootstrap 5 · Chart.js · ReportLab (PDF)
