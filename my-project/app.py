import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, g, session
from flask import Response
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, Regexp
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

# Ensure Flask uses the project's `templates` directory regardless of working directory
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

# Configuration (use environment variables in production)
app.config.update(
    SECRET_KEY=os.environ.get('FLASK_SECRET', 'dev-secret'),
    WTF_CSRF_ENABLED=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.environ.get('SESSION_SAMESITE', 'Lax'),
    SESSION_COOKIE_SECURE=(os.environ.get('FLASK_ENV') != 'development')
)


def get_db_connection():
    conn = sqlite3.connect(DATABASE, timeout=10)  # 10 second timeout if DB is locked
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode for concurrent writes
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    conn.commit()
    # Ensure `is_admin` column exists (for upgrades from earlier schema)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cur.fetchall()]
    if 'is_admin' not in cols:
        cur.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
        conn.commit()

    # Create notes table (for user-posted content with optional parent_note_id for replies)
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            parent_note_id INTEGER,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (parent_note_id) REFERENCES notes(id)
        )
        '''
    )
    conn.commit()

    # Create reactions table (emoji reactions to notes)
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(note_id, user_id, emoji),
            FOREIGN KEY (note_id) REFERENCES notes(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        '''
    )
    conn.commit()

    conn.close()

    # Optionally auto-create an admin user from environment variables
    admin_user = os.environ.get('ADMIN_USER')
    admin_pass = os.environ.get('ADMIN_PASS')
    if admin_user and admin_pass:
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        cur2.execute('SELECT id FROM users WHERE username = ?', (admin_user,))
        if not cur2.fetchone():
            hashed = generate_password_hash(admin_pass)
            # Environment-provided admin is the superadmin (level 2)
            cur2.execute('INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)', (admin_user, f'{admin_user}@local', hashed, 2))
            conn2.commit()
        conn2.close()


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    email = StringField('Email', validators=[DataRequired(), Regexp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', message='Enter a valid email address.')])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    terms = BooleanField('Terms', validators=[DataRequired()])


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember me')


class AdminActionForm(FlaskForm):
    pass


class PostNoteForm(FlaskForm):
    content = StringField('Note', validators=[DataRequired(), Length(min=1, max=500)])


class ReplyForm(FlaskForm):
    content = StringField('Reply', validators=[DataRequired(), Length(min=1, max=500)])


class ReactForm(FlaskForm):
    emoji = StringField('Emoji', validators=[DataRequired(), Length(min=1, max=10)])


class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    # new_password is optional; enforce length on submit only if provided
    new_password = PasswordField('New Password', description='Leave blank to keep current password')
    confirm_password = PasswordField('Confirm Password', validators=[EqualTo('new_password', message='Passwords must match')])


if hasattr(app, 'before_first_request'):
    @app.before_first_request
    def initialize_database():
        init_db()
else:
    # Older Flask versions may not have `before_first_request` decorator.
    # Initialize DB now as a fallback.
    try:
        init_db()
    except Exception:
        try:
            app.logger.exception('Failed to initialize database at import time')
        except Exception:
            pass


# Basic logging configuration for production
if not app.debug:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    app.logger.setLevel(logging.INFO)


# Log incoming requests (helps debug which URL the browser requests)
@app.before_request
def log_request_info():
    try:
        app.logger.info(f"Incoming request: {request.method} {request.path}")
    except Exception:
        pass


@app.route('/__debug')
def debug_info():
    """Return a small debug report: registered routes and template folder."""
    lines = []
    lines.append(f"template_folder: {app.template_folder}")
    lines.append(f"cwd: {os.getcwd()}")
    lines.append('')
    lines.append('Registered routes:')
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: str(r)):
        methods = ','.join(sorted(rule.methods))
        lines.append(f"{rule}  -> methods={methods}")
    text = '\n'.join(lines)
    return Response(text, mimetype='text/plain')


@app.route('/')
def home():
    # Render the home page with a preview of latest top-level notes
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT n.id, n.user_id, n.content, n.created_at, u.username
        FROM notes n
        JOIN users u ON n.user_id = u.id
        WHERE n.parent_note_id IS NULL
        ORDER BY n.created_at DESC
        LIMIT 5
    ''')
    notes_preview = cur.fetchall()
    conn.close()
    return render_template('index.html', notes_preview=notes_preview)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip()
        password = form.password.data

        conn = get_db_connection()
        cur = conn.cursor()

        # Check if username or email already exists
        cur.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        existing = cur.fetchone()
        if existing:
            flash('Username or email already registered.')
            conn.close()
            return render_template('register.html', form=form)

        hashed = generate_password_hash(password)
        cur.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed))
        conn.commit()
        conn.close()

        flash('Registration successful. You can now sign in.')
        return redirect(url_for('home'))

    # If GET or validation failed, render the form (flashed errors shown above)
    if form.errors:
        for field, errs in form.errors.items():
            for e in errs:
                flash(f"{field}: {e}")

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, username, email, password FROM users WHERE username = ?', (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            # Password is correct; log in the user
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            if form.remember_me.data:
                session.permanent = True
            flash(f'Welcome back, {user["username"]}!')
            return redirect(url_for('profile'))
        else:
            flash('Invalid username or password.')

    return render_template('login.html', form=form)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash('Please log in to view your profile.')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT username, email FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        flash('User not found.')
        return redirect(url_for('logout'))

    form = ProfileForm()
    if form.validate_on_submit():
        new_username = form.username.data.strip()
        new_password = form.new_password.data or ''

        # Check username uniqueness (exclude current user)
        cur.execute('SELECT id FROM users WHERE username = ? AND id != ?', (new_username, user_id))
        if cur.fetchone():
            flash('Username is already taken.')
            conn.close()
            return render_template('profile.html', username=user['username'], email=user['email'], form=form)

        # If provided, validate new password length
        if new_password and len(new_password) < 6:
            flash('New password must be at least 6 characters.')
            conn.close()
            return render_template('profile.html', username=user['username'], email=user['email'], form=form)

        # Perform update(s)
        if new_password:
            hashed = generate_password_hash(new_password)
            cur.execute('UPDATE users SET username = ?, password = ? WHERE id = ?', (new_username, hashed, user_id))
        else:
            cur.execute('UPDATE users SET username = ? WHERE id = ?', (new_username, user_id))

        conn.commit()
        conn.close()

        # Update session username
        session['username'] = new_username
        flash('Profile updated successfully.')
        return redirect(url_for('profile'))

    # Pre-fill form on GET
    form.username.data = user['username']
    conn.close()
    return render_template('profile.html', username=user['username'], email=user['email'], form=form)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('home'))


def admin_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            flash('Please login as admin to access that page.')
            return redirect(url_for('login'))
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,))
        row = cur.fetchone()
        conn.close()
        # Allow both regular admins (1) and superadmin (2) to view the admin page
        if not row or row['is_admin'] not in (1, 2):
            flash('You do not have permission to access that page.')
            return redirect(url_for('home'))
        return view_func(*args, **kwargs)

    return wrapped


@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    admin_form = AdminActionForm()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, username, email, is_admin, created_at FROM users ORDER BY id DESC')
    users = cur.fetchall()
    # Determine if current user is the configured superadmin
    current_user_id = session.get('user_id')
    is_superadmin = False
    admin_env_username = os.environ.get('ADMIN_USER')
    if current_user_id:
        cur.execute('SELECT username, is_admin FROM users WHERE id = ?', (current_user_id,))
        cur_row = cur.fetchone()
        # If ADMIN_USER is configured, require username match; otherwise any is_admin==2 is superadmin
        if cur_row and cur_row['is_admin'] == 2 and (not admin_env_username or cur_row['username'] == admin_env_username):
            is_superadmin = True

    conn.close()
    return render_template('admin.html', users=users, admin_form=admin_form, is_superadmin=is_superadmin)


@app.route('/admin/promote', methods=['POST'])
@admin_required
def admin_promote():
    form = AdminActionForm()
    if form.validate_on_submit():
        # Only the configured superadmin (is_admin==2 and username==ADMIN_USER) can promote/demote
        current_user_id = session.get('user_id')
        admin_env_username = os.environ.get('ADMIN_USER')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT username, is_admin FROM users WHERE id = ?', (current_user_id,))
        cur_row = cur.fetchone()
        # If ADMIN_USER is configured, require username match; otherwise any is_admin==2 qualifies
        if not cur_row or not (cur_row['is_admin'] == 2 and (not admin_env_username or cur_row['username'] == admin_env_username)):
            conn.close()
            flash('Only the superadmin can perform that action.')
            return redirect(url_for('admin'))

        user_id = request.form.get('user_id')
        action = request.form.get('action')
        if user_id and action in ('promote', 'demote'):
            # Prevent modifying the superadmin account
            cur.execute('SELECT username, is_admin FROM users WHERE id = ?', (user_id,))
            target = cur.fetchone()
            if target and target['is_admin'] == 2:
                conn.close()
                flash('Cannot modify the superadmin account.')
                return redirect(url_for('admin'))

            is_admin_val = 1 if action == 'promote' else 0
            cur.execute('UPDATE users SET is_admin = ? WHERE id = ?', (is_admin_val, user_id))
            conn.commit()
            conn.close()
            flash('User updated.')
    return redirect(url_for('admin'))


@app.route('/admin/delete', methods=['POST'])
@admin_required
def admin_delete():
    form = AdminActionForm()
    if form.validate_on_submit():
        # Only the configured superadmin (is_admin==2 and username==ADMIN_USER) can delete users
        current_user_id = session.get('user_id')
        admin_env_username = os.environ.get('ADMIN_USER')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT username, is_admin FROM users WHERE id = ?', (current_user_id,))
        cur_row = cur.fetchone()
        # If ADMIN_USER is configured, require username match; otherwise any is_admin==2 qualifies
        if not cur_row or not (cur_row['is_admin'] == 2 and (not admin_env_username or cur_row['username'] == admin_env_username)):
            conn.close()
            flash('Only the superadmin can perform that action.')
            return redirect(url_for('admin'))

        user_id = request.form.get('user_id')
        if user_id:
            # Prevent deleting superadmin account
            cur.execute('SELECT username, is_admin FROM users WHERE id = ?', (user_id,))
            target = cur.fetchone()
            if target and target['is_admin'] == 2:
                conn.close()
                flash('Cannot delete the superadmin account.')
                return redirect(url_for('admin'))

            cur.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            flash('User deleted.')
    return redirect(url_for('admin'))


# ===== NOTES ROUTES =====

@app.route('/notes', methods=['GET'])
def notes_list():
    """Display all top-level notes with replies nested underneath."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all top-level notes (parent_note_id IS NULL) ordered newest first
    cur.execute('''
        SELECT n.id, n.user_id, n.content, n.created_at, u.username
        FROM notes n
        JOIN users u ON n.user_id = u.id
        WHERE n.parent_note_id IS NULL
        ORDER BY n.created_at DESC
    ''')
    notes = cur.fetchall()
    
    # Build a dictionary to hold notes with their replies and reactions
    notes_data = []
    for note in notes:
        note_id = note['id']
        
        # Get replies for this note
        cur.execute('''
            SELECT n.id, n.user_id, n.content, n.created_at, u.username
            FROM notes n
            JOIN users u ON n.user_id = u.id
            WHERE n.parent_note_id = ?
            ORDER BY n.created_at ASC
        ''', (note_id,))
        replies = cur.fetchall()
        
        # Get reactions for this note
        cur.execute('''
            SELECT emoji, COUNT(*) as count
            FROM reactions
            WHERE note_id = ?
            GROUP BY emoji
            ORDER BY count DESC
        ''', (note_id,))
        reactions = cur.fetchall()
        
        # Check if current user has reacted with each emoji
        user_reactions = set()
        cur.execute('''
            SELECT DISTINCT emoji
            FROM reactions
            WHERE note_id = ? AND user_id = ?
        ''', (note_id, session['user_id']))
        for row in cur.fetchall():
            user_reactions.add(row['emoji'])
        
        # Get reactions for replies too
        reply_reactions = {}
        for reply in replies:
            reply_id = reply['id']
            cur.execute('''
                SELECT emoji, COUNT(*) as count
                FROM reactions
                WHERE note_id = ?
                GROUP BY emoji
                ORDER BY count DESC
            ''', (reply_id,))
            reply_reactions[reply_id] = cur.fetchall()
        
        # Check if current user has reacted to each reply
        reply_user_reactions = {}
        for reply in replies:
            reply_id = reply['id']
            cur.execute('''
                SELECT DISTINCT emoji
                FROM reactions
                WHERE note_id = ? AND user_id = ?
            ''', (reply_id, session['user_id']))
            reply_user_reactions[reply_id] = {row['emoji'] for row in cur.fetchall()}
        
        notes_data.append({
            'note': note,
            'replies': replies,
            'reactions': reactions,
            'user_reactions': user_reactions,
            'reply_reactions': reply_reactions,
            'reply_user_reactions': reply_user_reactions
        })
    
    conn.close()
    form = PostNoteForm()
    return render_template('notes.html', notes_data=notes_data, form=form)


@app.route('/notes/create', methods=['POST'])
def create_note():
    """Create a new top-level note."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    form = PostNoteForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO notes (user_id, content)
            VALUES (?, ?)
        ''', (session['user_id'], form.content.data))
        conn.commit()
        conn.close()
        flash('Note posted!')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}')
    
    return redirect(url_for('notes_list'))


@app.route('/notes/<int:note_id>/reply', methods=['POST'])
def create_reply(note_id):
    """Create a reply to an existing note."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    form = ReplyForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify parent note exists
        cur.execute('SELECT id FROM notes WHERE id = ?', (note_id,))
        if cur.fetchone():
            cur.execute('''
                INSERT INTO notes (user_id, parent_note_id, content)
                VALUES (?, ?, ?)
            ''', (session['user_id'], note_id, form.content.data))
            conn.commit()
            flash('Reply posted!')
        else:
            flash('Note not found.')
        
        conn.close()
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}')
    
    return redirect(url_for('notes_list'))


@app.route('/notes/<int:note_id>/react', methods=['POST'])
def react_to_note(note_id):
    """Add an emoji reaction to a note."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    emoji = request.form.get('emoji', '').strip()
    
    if not emoji:
        flash('Invalid emoji.')
        return redirect(url_for('notes_list'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Verify note exists
    cur.execute('SELECT id FROM notes WHERE id = ?', (note_id,))
    if not cur.fetchone():
        flash('Note not found.')
        conn.close()
        return redirect(url_for('notes_list'))
    
    # Check if user already reacted with this emoji
    cur.execute('''
        SELECT id FROM reactions
        WHERE note_id = ? AND user_id = ? AND emoji = ?
    ''', (note_id, session['user_id'], emoji))
    
    if cur.fetchone():
        # Remove reaction if already exists (toggle)
        cur.execute('''
            DELETE FROM reactions
            WHERE note_id = ? AND user_id = ? AND emoji = ?
        ''', (note_id, session['user_id'], emoji))
        flash('Reaction removed.')
    else:
        # Add new reaction
        try:
            cur.execute('''
                INSERT INTO reactions (note_id, user_id, emoji)
                VALUES (?, ?, ?)
            ''', (note_id, session['user_id'], emoji))
            flash('Reaction added!')
        except sqlite3.IntegrityError:
            flash('You already reacted with that emoji.')
    
    conn.commit()
    conn.close()
    return redirect(url_for('notes_list'))


if __name__ == '__main__':
    # Ensure DB exists before first run
    init_db()
    app.run(debug=True)

