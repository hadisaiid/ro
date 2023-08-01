from app import app, mysql
from flask import render_template, request, redirect, url_for, flash, session, jsonify, abort, make_response
from functools import wraps

from werkzeug.utils import secure_filename

import uuid
import os


from flask_bcrypt import Bcrypt
bcrypt = Bcrypt(app)

############## START HELPERS #########################
def get_courses():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM course")
    return cursor.fetchall();
 
def update_course_in_db(course_id, updated_title, updated_description):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE course SET title=%s, description=%s WHERE id=%s",
                       (updated_title, updated_description, course_id))
        mysql.connection.commit()

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        db.rollback()
        flash("An error occurred while updating the course.", 'danger')

def fetch_course_by_id(course_id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM course WHERE id=%s", (course_id,))
        course = cursor.fetchone()
        return course
    except mysql.connector.Error as err:
        print(f"Error: {err}")

def delete_course_from_db(course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM course WHERE id=%s", (course_id,))
    mysql.connection.commit()

    flash("Course deleted successfully!", 'success')
    
def save_video_to_db(title, path, course_id):
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO video (title, path, course_id) VALUES (%s, %s, %s)",
                       (title, path, course_id))
        mysql.connection.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")


def save_file_to_db(title, path, course_id):
    cursor = mysql.connection.cursor()

    cursor.execute("INSERT INTO file (title, path, course_id) VALUES (%s, %s, %s)",
                    (title, path, course_id))
    mysql.connection.commit()


def save_new_thread_to_db(title, course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO Thread (Title, course_id) VALUES (%s, %s)", (title, course_id))

    thread_id = cursor.lastrowid
    mysql.connection.commit()

    return thread_id

def save_new_message_to_db(content, from_user_id, thread_id):
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO Message (content, `from`, `to`, thread_id) VALUES (%s, %s, %s, %s)",
                    (content, from_user_id, from_user_id, thread_id))
    mysql.connection.commit()
   

def save_quiz_submission_to_db(user_id, quiz_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM quiz_submission WHERE user_id=%s AND quiz_id=%s", (user_id, quiz_id))
    if cursor.fetchone() is not None:
        return
    cursor.execute("INSERT INTO quiz_submission (user_id, quiz_id) VALUES (%s, %s)",
                   (user_id, quiz_id))
    mysql.connection.commit()


    
############## END HELPERS ######################







############# Start Decorators ##############

def login_required(view_func):
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if 'user_id' in session:
            return view_func(*args, **kwargs)
        else:
            return redirect(url_for('login'))
    return decorated_view

def instructor_required(view_func):
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if 'user_id' in session and session['role'] == 'instructor':
            return view_func(*args, **kwargs)
        else:
            # User is not authenticated or does not have the required role
            return redirect(url_for('login'))
    return decorated_view

############# End Decorators ##############

@app.route("/")
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM course")
    rows = cur.fetchall()
    cur.close()
    return render_template('index.html', courses=rows)


@app.route("/about")
def about_us():
    return render_template('about.html')


@app.route("/courses")
def all_courses():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM course")
    rows = cur.fetchall()
    cur.close()
    return render_template('courses.html', courses=rows)



@app.route("/course/<id>")
def course(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM course WHERE id=%s", (id,))
    course = cur.fetchone()
    if course == None: 
        abort(404)
    cur.execute("SELECT * FROM user WHERE id=%s", (course[4],))
    instructor = cur.fetchone()
    cur.close()
    if('user_id' in session):
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_course WHERE user_id = %s AND course_id = %s", (session['user_id'], id))
        count = cursor.fetchone()[0]
        if(count > 0):
            progress = calculate_user_progress(session['user_id'], id)
            return render_template('course.html', course=course, instructor=instructor, progress=progress)
    return render_template('course.html', course=course, instructor=instructor)



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        cursor = mysql.connection.cursor()
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        role = "student"

        cursor.execute("SELECT id FROM user WHERE email=%s", (email,))
        if cursor.fetchone() is not None:
            return "Email already registered. Please use a different email."

        cursor.execute("INSERT INTO user (full_name, email, pass, role) VALUES (%s, %s, %s, %s)", (full_name, email, password, role))
        mysql.connection.commit();
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cursor = mysql.connection.cursor()
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT id, full_name, role FROM user WHERE email=%s AND pass=%s", (email, password))
        user = cursor.fetchone()

        if user is not None:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['role'] = user[2]
            if( session['role'] == 'instructor'):
                return redirect(url_for('instructor_dashboard'));
            return redirect(url_for('dashboard'))
        else:
            return "Invalid login credentials. Please try again."

    return render_template('login.html')


@app.route('/instructor_dashboard')
@login_required
@instructor_required
def instructor_dashboard():
    return render_template('instructor_dashboard.html')
    
@app.route('/new_course', methods=['GET', 'POST'])
@login_required
@instructor_required
def new_course():
    cursor = mysql.connection.cursor()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']

        file = request.files['cover']

        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"

        os.makedirs(app.config['UPLOAD_FILES_FOLDER'], exist_ok=True)

        file.save(os.path.join(app.config['UPLOAD_FILES_FOLDER'], filename))

        cursor.execute("INSERT INTO course (title, description, cover, instructor_id) VALUES (%s, %s, %s, %s)", (title, description, filename, session['user_id']))
        
        mysql.connection.commit();
        
        flash("New course added successfully!", "success")
        return redirect(url_for('instructor_dashboard'))

    return render_template('new_course.html')


@app.route('/instructor_dashboard/videos', methods=['GET', 'POST'])
@login_required
def user_videos():
    if request.method == 'POST':
        video_id = request.form.get('video_id')
        delete_video(video_id)
        flash('Video deleted successfully!', 'success')
        return redirect(url_for('user_videos'))

    user_videos = get_user_videos()

    return render_template('user_videos.html', user_videos=user_videos)

def get_user_videos():
    user_id = session['user_id']  
    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT v.id, v.title, v.path, c.title AS course_title, c.description AS course_description
        FROM Video v
        JOIN Course c ON v.course_id = c.id
        WHERE c.instructor_id = %s
    """, [user_id])

    user_videos = cursor.fetchall()
    return user_videos

@app.route('/delete_video/<int:video_id>', methods=['post'])
@login_required
@instructor_required
def delete_video(video_id):
    cursor = mysql.connection.cursor()
    video_path = get_video_path(video_id)
    if video_path:
        if os.path.exists(video_path):
            os.remove(video_path)
    cursor.execute("DELETE FROM video WHERE id = %s", (video_id,))
    mysql.connection.commit()

    return jsonify('ok')


def get_video_path(video_id):
    cursor = mysql.connection.cursor()

    cursor.execute("SELECT * FROM video WHERE id = %s", (video_id,))
    file_name = cursor.fetchone()[2]

    files_directory = 'app/static/videos'
    path = os.path.join(files_directory, file_name)
    return path

@app.route('/instructor_dashboard/files', methods=['GET', 'POST'])
@login_required
def user_files():
    if request.method == 'POST':
        file_id = request.form.get('file_id')
        delete_file(file_id)
        flash('File deleted successfully!', 'success')
        return redirect(url_for('user_files'))

    user_files = get_user_files()

    return render_template('user_files.html', user_files=user_files)

def get_user_files():
    user_id = session['user_id']  
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT f.id, f.title, f.path, c.title AS course_title, c.description AS course_description
        FROM File f
        JOIN Course c ON f.course_id = c.id
        WHERE c.instructor_id = %s
    """, (user_id,))
    user_files = cursor.fetchall()
    return user_files

@app.route('/delete_file/<int:file_id>', methods=['post'])
@login_required
@instructor_required
def delete_file(file_id):
    cursor = mysql.connection.cursor()
    file_path = get_file_path(file_id)
    if file_path:
        if os.path.exists(file_path):
            os.remove(file_path)
    cursor.execute("DELETE FROM file WHERE id = %s", (file_id,))
    mysql.connection.commit()
    return jsonify('ok')

def get_file_path(file_id):
    cursor = mysql.connection.cursor()

    cursor.execute("SELECT * FROM file WHERE id = %s", (file_id,))
    file_name = cursor.fetchone()[2]

    files_directory = 'app/static/files'
    path = os.path.join(files_directory, file_name)
    return path


@app.route('/instructor_dashboard/exams', methods=['GET', 'POST'])
@login_required
def user_exams():
    if request.method == 'POST':
        exam_id = request.form.get('exam_id')
        delete_exam(exam_id)
        flash('Exam deleted successfully!', 'success')
        return redirect(url_for('user_exams'))

    user_exams = get_user_exams()

    return render_template('user_exams.html', user_exams=user_exams)

def get_user_exams():
    cursor = mysql.connection.cursor()
    user_id = session['user_id']  

    cursor.execute("""
        SELECT e.id, e.title, e.duration
        FROM Exam e
        JOIN Course_Exam ce ON e.id = ce.exam_id
        JOIN Course c ON ce.course_id = c.id
        WHERE c.instructor_id = %s
    """, (user_id,))

    user_exams = cursor.fetchall()
    return user_exams

@app.route('/delete_exam/<int:exam_id>', methods=['post'])
@login_required
@instructor_required
def delete_exam(exam_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM exam WHERE id = %s", (exam_id,))
    mysql.connection.commit()
    return True



@app.route('/edit_courses')
@login_required
@instructor_required
def edit_courses():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM course WHERE instructor_id=%s", [session['user_id']])
    courses = cursor.fetchall()

    return render_template('edit_courses.html', courses=courses)


@app.route('/update_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
@instructor_required
def update_course(course_id):
    course = fetch_course_by_id(course_id)

    if request.method == 'POST':
        updated_title = request.form['title']
        updated_description = request.form['description']

        update_course_in_db(course_id, updated_title, updated_description)

        flash("Course updated successfully!", 'success')
        return redirect(url_for('edit_courses'))

    return render_template('update_course.html', course=course)


@app.route('/delete_course/<int:course_id>', methods=['POST'])
@login_required
@instructor_required
def delete_course(course_id):
    delete_course_from_db(course_id)

    flash("Course deleted successfully!", 'success')
    return redirect(url_for('edit_courses'))


@app.route('/upload_video', methods=['GET', 'POST'])
@login_required
@instructor_required
def upload_video():
    if request.method == 'POST':
        title = request.form['title']
        course_id = request.form['course']

        if 'video' not in request.files:
            flash('No file inserted', 'danger')
            return redirect(request.url)

        video_file = request.files['video']

        if video_file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        if allowed_file(video_file.filename):
            filename = secure_filename(f"{uuid.uuid4().hex}_{video_file.filename}")
            video_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            save_video_to_db(title, filename, course_id)
            flash('Video uploaded successfully!', 'success')
            return redirect(url_for('instructor_dashboard'))
        else:
            flash('Invalid file type', 'danger')
            return redirect(request.url)

    return render_template('new_video.html', courses=get_courses())

@app.route('/upload_file', methods=['GET', 'POST'])
@login_required
@instructor_required
def upload_file():
    if request.method == 'POST':
        title = request.form['title']
        course_id = request.form['course']

        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"

        os.makedirs(app.config['UPLOAD_FILES_FOLDER'], exist_ok=True)

        file.save(os.path.join(app.config['UPLOAD_FILES_FOLDER'], filename))

        save_file_to_db(title, filename, course_id)

        flash('File uploaded successfully!', 'success')
        return redirect(url_for('instructor_dashboard'))

    return render_template('upload_file.html', courses=get_courses())


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mkv', 'mov'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/dashboard')
@login_required
def dashboard():
    cursor = mysql.connection.cursor()
    query = "SELECT course.* FROM course " \
        "JOIN user_course ON course.id = user_course.course_id " \
        "WHERE user_course.user_id = %s"

    cursor.execute(query, (session['user_id'],))
    courses = cursor.fetchall()
    return render_template('user_dashboard.html', courses=courses)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('login'))

@app.route("/profile/<user_id>")
def profile(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM course WHERE id = " + id)
    row = cur.fetchone()
    cur.close()
    return render_template('course.html', course=row)



@app.route('/enroll/<course_id>')
@login_required
def enroll(course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM user_course WHERE user_id=%s AND course_id=%s", (session['user_id'], course_id))
    if cursor.fetchone() is not None:
        return study(course_id, '-1')
    cursor.execute("INSERT INTO user_course (user_id, course_id) VALUES (%s, %s)",
                    (session['user_id'], course_id))
    mysql.connection.commit()
    return study(course_id, video_id='-1')


@app.route('/study/<course_id>/<video_id>')
@login_required
def study(course_id, video_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM course WHERE id=%s", (course_id,))
    course = cursor.fetchone()
    cursor.execute("SELECT * FROM user WHERE id=%s", (course[4],))
    instructor = cursor.fetchone();
    cursor.execute("SELECT * FROM video WHERE course_id=%s", (course_id,))
    videos = cursor.fetchall()
    cursor.execute("SELECT * FROM file WHERE course_id=%s", (course_id,))
    files = cursor.fetchall()
    if(video_id == '-1'):
        cursor.execute("SELECT * FROM video WHERE course_id=%s LIMIT 1", (course_id,))
        current_video = cursor.fetchone()
    else:
        cursor.execute("SELECT * FROM video WHERE id=%s", [video_id])
        current_video = cursor.fetchone()

    cursor.execute("SELECT * FROM exam JOIN course_exam ON exam.id = course_exam.exam_id WHERE course_exam.course_id = " + course_id)
    exams = cursor.fetchall()

    cursor.execute("SELECT * FROM thread WHERE course_id=%s", (course_id,))
    threads = cursor.fetchall()

    if(current_video is None):
        return render_template('study_course.html', 
        current_video=None, 
        course=course, 
        instructor=instructor, 
        no_videos="Course has No Videos, Yet.",
        files=files,
        exams=exams,
        threads=threads)

    return render_template('study_course.html', 
        course=course, 
        instructor=instructor, 
        videos=videos, 
        current_video=current_video, 
        files=files,
        exams=exams,
        threads=threads)





@app.route('/new_thread', methods=['GET', 'POST'])
@login_required
@instructor_required
def new_thread():
    if request.method == 'POST':
        title = request.form['title']
        course_id = request.form['course']
        thread_id = save_new_thread_to_db(title, course_id)

        flash("New thread created successfully!", 'success')
        return redirect(url_for('thread', id=thread_id))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM course")
    courses = cursor.fetchall()

    return render_template('new_thread.html', courses=courses)



@app.route('/new_message/<int:thread_id>', methods=['GET', 'POST'])
@login_required
def new_message(thread_id):
    if request.method == 'POST':
        content = request.form['content']
        user_id = session['user_id']

        save_new_message_to_db(content, user_id, thread_id)

        flash("New message created successfully!", 'success')
        return redirect(url_for('thread', id=thread_id))

    return render_template('new_message.html')


@app.route('/thread/<int:id>', methods=['GET'])
@login_required
def thread(id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM thread WHERE id=%s", (id,))
    thread = cursor.fetchone()
    cursor.execute("SELECT m.*, u.full_name AS author_name FROM message m JOIN user u ON m.from = u.id WHERE thread_id=%s", (id,))
    messages = cursor.fetchall()
    return render_template('thread.html', thread=thread, messages=messages);

@app.route('/new_exam', methods=['GET', 'POST'])
@login_required 
def new_exam():
    if request.method == 'POST':
        content = request.form['exam']
        course_id = request.form['course']
        title = request.form['title']
        duration = request.form['duration']
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO exam (duration, title, exam) VALUES (%s, %s, %s)",
                        (duration, title, content))
        mysql.connection.commit()
        exam_id = cursor.lastrowid

        cursor.execute("INSERT INTO course_exam (course_id, exam_id) VALUES (%s, %s)", (course_id, exam_id))
        mysql.connection.commit()

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM course")
    courses = cursor.fetchall()
    return render_template('new_exam.html', courses=courses)

@app.route('/exam_duration/<int:id>')
def exam_duration(id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM exam WHERE id = %s", (id,))
    return jsonify(cursor.fetchone()[1])

@app.route('/take_exam/<int:id>/<int:course_id>', methods=['GET', 'POST'])
@login_required
def take_exam(id, course_id):
    return render_template("take_exam.html", exam_id=id, course_id=course_id)


@app.route('/get_exam/<int:id>', methods=['GET', 'POST'])
@login_required
def get_exam(id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM exam WHERE id = " + str(id))
    exam = cursor.fetchone()
    return jsonify(exam)

@app.route('/submit_quiz/<int:course_id>/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def submit_quiz(course_id, quiz_id):
    user_id = session['user_id']

    save_quiz_submission_to_db(user_id, quiz_id)

    calculate_and_update_course_progress(user_id, course_id)

    flash("Quiz submitted successfully!", 'success')
    return redirect(url_for('study', course_id=course_id, video_id='-1'))



def calculate_and_update_course_progress(user_id, course_id):
    cursor = mysql.connection.cursor()

    total_quizzes = get_total_quizzes_for_course(course_id)

    quizzes_submitted = get_quizzes_submitted_by_user(user_id, course_id)

    quiz_progress = quizzes_submitted / total_quizzes

    cursor.execute("UPDATE user_course SET progress = %s WHERE user_id = %s AND course_id = %s",
                   (quiz_progress, user_id, course_id))
    mysql.connection.commit()


def get_total_quizzes_for_course(course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM course_exam WHERE course_id = %s", (course_id,))
    total_quizzes = cursor.fetchone()[0]
    return total_quizzes

def get_quizzes_submitted_by_user(user_id, course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM quiz_submission WHERE user_id = %s AND quiz_id IN (SELECT exam_id FROM course_exam WHERE course_id = %s)", (user_id, course_id))
    quizzes_submitted = cursor.fetchone()[0]
    return quizzes_submitted


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        cursor = mysql.connection.cursor()
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT id FROM Admin WHERE username = %s AND password = %s",
                       (username, password))
        admin_id = cursor.fetchone()

        if admin_id:
            session['admin_id'] = admin_id[0]
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' in session:
        return render_template('admin_dashboard.html')
    else:
        flash('Please log in as an admin to access the dashboard.', 'danger')
        return redirect(url_for('admin_login'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('admin_login'))


@app.route('/admin/view_users')
def view_users():
    if 'admin_id' in session:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, full_name, email, role FROM user")
        users = cursor.fetchall()
        return render_template('view_users.html', users=users)
    else:
        flash('Please log in as an admin to access the dashboard.', 'danger')
        return redirect(url_for('admin_login'))


@app.route('/admin/update_user/<int:user_id>', methods=['GET', 'POST'])
def update_user(user_id):
    if 'admin_id' in session:
        if request.method == 'POST':
            full_name = request.form['full_name']
            email = request.form['email']
            role = request.form['role']

            update_user_in_db(user_id, full_name, email, role)

            flash("User updated successfully!", 'success')
            return redirect(url_for('view_users'))
        else:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT * FROM user WHERE id=%s", (user_id,))
            user_data = cursor.fetchone()
            return render_template('update_user.html', user_data=user_data)
    else:
        flash('Please log in as an admin to access the dashboard.', 'danger')
        return redirect(url_for('admin_login'))

def update_user_in_db(user_id, full_name, email, role):
    cursor = mysql.connection.cursor()

    update_query = "UPDATE user SET full_name = %s, email = %s, role = %s WHERE id = %s"
    data = (full_name, email, role, user_id)
    cursor.execute(update_query, data)

    mysql.connection.commit()
    


@app.route('/admin/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'admin_id' in session:
        if user_exists(user_id):
            delete_user_from_db(user_id)

            return jsonify({'message': 'User deleted successfully'}), 200
        else:
            return jsonify({'message': 'User not found'}), 404
    else:
        return jsonify({'message': 'Unauthorized access'}), 401

def user_exists(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM user WHERE id = %s", (user_id,))
    user_count = cursor.fetchone()[0]
    return user_count > 0

def delete_user_from_db(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM user WHERE id = %s", (user_id,))
    mysql.connection.commit()


@app.route('/admin/create_user', methods=['GET', 'POST'])
def create_user():
    if 'admin_id' in session:
        if request.method == 'POST':
            full_name = request.form['full_name']
            email = request.form['email']
            role = request.form['role']
            password = request.form['password']  

            create_new_user(full_name, email, role, password)

            flash("User created successfully!", 'success')
            return redirect(url_for('view_users'))
        else:
            return render_template('create_user.html')
    else:
        flash('Please log in as an admin to access the dashboard.', 'danger')
        return redirect(url_for('admin_login'))



def create_new_user(full_name, email, role, password):
    cursor = mysql.connection.cursor()

    insert_query = "INSERT INTO user (full_name, email, role, pass) VALUES (%s, %s, %s, %s)"
    data = (full_name, email, role, bcrypt.generate_password_hash
                            (password).decode('utf-8'))
    cursor.execute(insert_query, data)

    mysql.connection.commit()



@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    cursor = mysql.connection.cursor()
    user_id = session['user_id']

    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        current_password = request.form['current_password']
        new_password = request.form['new_password']

        if validate_current_password(user_id, current_password):
            update_user_info(user_id, full_name, email)

            if new_password:
                update_user_password(user_id, new_password)

            flash("Account information updated successfully!", 'success')
            return redirect(url_for('account'))
        else:
            flash("Current password is incorrect. Changes were not saved.", 'danger')
            return redirect(url_for('account'))
    else:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, full_name, email FROM user WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        return render_template('account.html', user_data=user_data)
   

def validate_current_password(user_id, current_password):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT pass FROM user WHERE id = %s", (user_id,))
    password = cursor.fetchone()[0]
    return current_password == password

def update_user_info(user_id, full_name, email):
    cursor = mysql.connection.cursor()
    update_query = "UPDATE user SET full_name = %s, email = %s WHERE id = %s"
    data = (full_name, email, user_id)
    cursor.execute(update_query, data)
    mysql.connection.commit()

    

def update_user_password(user_id, new_password):
    cursor = mysql.connection.cursor()
    update_query = "UPDATE user SET pass = %s WHERE id = %s"
    data = (new_password, user_id)
    cursor.execute(update_query, data)
    mysql.connection.commit()
   




















def calculate_user_progress(user_id, course_id):
    total_exams = get_total_exams_for_course(course_id)
    if(total_exams > 0):
        progress_percentage = (get_submitted_exams_for_user_course(user_id, course_id) / total_exams) * 100
        progress_percentage = round(progress_percentage, 2)
        return progress_percentage
    return 0



def get_total_exams_for_course(course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM course_exam WHERE course_id = %s", (course_id,))
    total_exams = cursor.fetchone()[0]
    return total_exams


    

@app.route('/download_certificate/<int:user_id>/<int:course_id>/<format>')
@login_required
def download_certificate(user_id, course_id, format):
    if user_completed_course(user_id, course_id):
        certificate_data = generate_certificate_data(user_id, course_id)
        if format == 'pdf':
            certificate_pdf = generate_certificate_pdf(certificate_data)
            return send_pdf(certificate_pdf, certificate_data['full_name'], 'certificate')
        elif format == 'png':
            certificate_png = generate_certificate_png(certificate_data)
            return send_png(certificate_png, certificate_data['full_name'], 'certificate')
        else:
            flash("Invalid format requested.", 'danger')
            return redirect(url_for('dashboard'))
    else:
        flash("Sorry, you have not completed the course yet.", 'danger')
        return redirect(url_for('dashboard'))



def user_completed_course(user_id, course_id):
    total_quizzes = get_total_quizzes_for_course(course_id)
    quizzes_submitted = get_quizzes_submitted_by_user(user_id, course_id)
    return quizzes_submitted == total_quizzes

def get_total_quizzes_for_course(course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM course_exam WHERE course_id = %s", (course_id,))
    total_quizzes = cursor.fetchone()[0]

    return total_quizzes
   
def get_submitted_exams_for_user_course(user_id, course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM quiz_submission INNER JOIN course_exam ON quiz_submission.quiz_id = course_exam.exam_id WHERE quiz_submission.user_id = %s AND course_exam.course_id = %s",
               (user_id, course_id))
    submitted_exams = cursor.fetchone()[0]

    return submitted_exams

from datetime import date

def generate_certificate_data(user_id, course_id):
    user_full_name = get_user_full_name(user_id)

    course_title = get_course_title(course_id)

    completion_date = date.today().strftime('%Y-%m-%d')

    certificate_data = {
        'full_name': user_full_name,
        'course_title': course_title,
        'completion_date': completion_date,
    }

    return certificate_data


def get_user_full_name(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT full_name FROM user WHERE id = %s", (user_id,))
    user_full_name = cursor.fetchone()[0]

    return user_full_name

def get_course_title(course_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT title FROM course WHERE id = %s", (course_id,))
    course_title = cursor.fetchone()[0]

    return course_title

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

def generate_certificate_pdf(certificate_data):
    logo_img = Image.open('app/static/assets/logo.png')

    logo_position = (50, 50)

    image = Image.new('RGB', (1000, 600), color='white')
    draw = ImageDraw.Draw(image)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(name='TitleStyle', parent=styles['Heading1'], fontSize=24, textColor=colors.blue)
    style_body = ParagraphStyle(name='BodyStyle', parent=styles['Normal'], fontSize=12)

    title = f"Certificate of Completion"
    name = f"Presented to: {certificate_data['full_name']}"
    course = f"For successfully completing the course: {certificate_data['course_title']}"
    date = f"Completion Date: {certificate_data['completion_date']}"


    content = [Paragraph(title, style_title), Paragraph(name, style_body), Paragraph(course, style_body), Paragraph(date, style_body)]

    doc.build(content)
    pdf_data = buffer.getvalue()
    buffer.close()

    return pdf_data

def generate_certificate_png(certificate_data):
    logo_img = Image.open('app/static/assets/logo.png')

    logo_position = (50, 50)

    image = Image.new('RGB', (1000, 600), color='white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", size=30)
    image.paste(logo_img, logo_position)

    x, y = 50, 300
    draw.text((x, y), "Certificate of Completion", fill="black", font=font)
    draw.text((x, y + 100), f"Presented to: {certificate_data['full_name']}", fill="black", font=font)
    draw.text((x, y + 200), f"For successfully completing the course: {certificate_data['course_title']}", fill="black", font=font)
    draw.text((x, y + 300), f"Completion Date: {certificate_data['completion_date']}", fill="black", font=font)

    buffer = BytesIO()
    image.save(buffer, format='PNG')
    png_data = buffer.getvalue()
    buffer.close()

    return png_data


from flask import Response

def send_pdf(pdf_data, file_name, file_type):
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={file_name}_{file_type}.pdf'
    return response

def send_png(png_data, file_name, file_type):
    response = make_response(png_data)
    response.headers['Content-Type'] = 'image/png'
    response.headers['Content-Disposition'] = f'attachment; filename={file_name}_{file_type}.png'
    return response
