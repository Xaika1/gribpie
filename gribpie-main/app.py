from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_bcrypt import Bcrypt
import os
import uuid
import qrcode
from io import BytesIO
from datetime import datetime
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gribpie_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/www/xaika.ru/site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/var/www/xaika.ru/uploads'
app.config['MAX_CONTENT_LENGTH'] = 262144000
app.config['BASE_URL'] = 'https://xaika.ru'
app.config['MAX_FILES_PER_PROJECT'] = 50

bcrypt = Bcrypt(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    shared_projects = db.relationship('ProjectAccess', backref='user', lazy=True)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    storage_used = db.Column(db.Integer, default=0)
    files = db.relationship('File', backref='project', lazy=True)
    shared_links = db.relationship('SharedLink', backref='project', lazy=True)
    access = db.relationship('ProjectAccess', backref='project', lazy=True)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

class SharedLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(36), unique=True, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProjectAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    access_level = db.Column(db.String(10), default='view')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.template_filter('format_size')
def format_size(bytes):
    if bytes >= 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024 * 1024):.2f} ГБ"
    elif bytes >= 1024 * 1024:
        return f"{bytes / (1024 * 1024):.2f} МБ"
    elif bytes >= 1024:
        return f"{bytes / 1024:.2f} КБ"
    else:
        return f"{bytes} Б"

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'Файл слишком большой. Максимальный размер: 250 МБ'}), 413

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже существует', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email уже зарегистрирован', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Регистрация успешна! Пожалуйста, войдите.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Неверные учетные данные', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    personal_projects = Project.query.filter_by(user_id=current_user.id).all()
    
    shared_projects = []
    for access in current_user.shared_projects:
        project = Project.query.get(access.project_id)
        if project:
            shared_projects.append({
                'project': project,
                'access_level': access.access_level
            })
    
    all_users = User.query.filter(User.id != current_user.id).all()
    
    return render_template('dashboard.html', 
                          personal_projects=personal_projects,
                          shared_projects=shared_projects,
                          all_users=all_users)

@app.route('/all-files')
@login_required
def all_files():
    personal_projects = Project.query.filter_by(user_id=current_user.id).all()
    shared_projects = []
    
    for access in current_user.shared_projects:
        project = Project.query.get(access.project_id)
        if project:
            shared_projects.append({
                'project': project,
                'access_level': access.access_level
            })
    
    all_files = []
    
    for project in personal_projects:
        files = File.query.filter_by(project_id=project.id).all()
        for file in files:
            all_files.append({
                'id': file.id,
                'filename': file.filename,
                'size': file.size,
                'project_name': project.name,
                'project_id': project.id,
                'access_level': 'owner'
            })
    
    for item in shared_projects:
        project = item['project']
        files = File.query.filter_by(project_id=project.id).all()
        for file in files:
            all_files.append({
                'id': file.id,
                'filename': file.filename,
                'size': file.size,
                'project_name': project.name,
                'project_id': project.id,
                'access_level': item['access_level']
            })
    
    return render_template('all_files.html', files=all_files)

@app.route('/create_project', methods=['POST'])
@login_required
def create_project():
    name = request.form['name']
    if not name or len(name) < 3:
        flash('Название проекта должно содержать минимум 3 символа', 'danger')
        return redirect(url_for('dashboard'))
    
    new_project = Project(name=name, user_id=current_user.id)
    db.session.add(new_project)
    db.session.commit()
    
    flash('Проект успешно создан!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/upload/<int:project_id>', methods=['POST'])
@login_required
def upload_file(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        access = ProjectAccess.query.filter_by(project_id=project_id, user_id=current_user.id).first()
        if not access or access.access_level != 'edit':
            flash('У вас нет прав на загрузку файлов в этот проект', 'danger')
            return redirect(url_for('dashboard'))
    
    files_count = File.query.filter_by(project_id=project_id).count()
    if files_count >= app.config['MAX_FILES_PER_PROJECT']:
        flash(f'Превышен лимит файлов в проекте ({app.config["MAX_FILES_PER_PROJECT"]})!', 'danger')
        return redirect(url_for('dashboard'))
    
    if 'file' not in request.files:
        flash('Не выбран файл', 'danger')
        return redirect(request.referrer)
    
    file = request.files['file']
    if file.filename == '':
        flash('Не выбран файл', 'danger')
        return redirect(request.referrer)
    
    file_size = len(file.read())
    if project.storage_used + file_size > 262144000:
        flash(f'Недостаточно места на сервере. Осталось только {format_size(262144000 - project.storage_used)}.', 'danger')
        return redirect(request.referrer)
    
    file.seek(0)
    filename = file.filename
    project_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(project.id))
    os.makedirs(project_dir, exist_ok=True)
    
    file_path = os.path.join(project_dir, filename)
    file.save(file_path)
    
    new_file = File(filename=filename, path=file_path, size=file_size, project_id=project.id)
    db.session.add(new_file)
    project.storage_used += file_size
    db.session.commit()
    
    flash('Файл успешно загружен!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    file = File.query.get_or_404(file_id)
    project = Project.query.get_or_404(file.project_id)
    
    if project.user_id != current_user.id:
        access = ProjectAccess.query.filter_by(project_id=project.id, user_id=current_user.id).first()
        if not access:
            flash('У вас нет доступа к этому файлу', 'danger')
            return redirect(url_for('dashboard'))
    
    return send_file(file.path, as_attachment=True, download_name=file.filename)

@app.route('/delete/<int:file_id>')
@login_required
def delete_file(file_id):
    file = File.query.get_or_404(file_id)
    project = Project.query.get_or_404(file.project_id)
    
    if project.user_id != current_user.id:
        access = ProjectAccess.query.filter_by(project_id=project.id, user_id=current_user.id).first()
        if not access or access.access_level != 'edit':
            flash('У вас нет прав на удаление файлов в этом проекте', 'danger')
            return redirect(url_for('dashboard'))
    
    project.storage_used -= file.size
    db.session.delete(file)
    db.session.commit()
    
    flash('Файл успешно удален!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_project/<int:project_id>')
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('У вас нет прав на удаление этого проекта', 'danger')
        return redirect(url_for('dashboard'))
    
    files = File.query.filter_by(project_id=project_id).all()
    for file in files:
        if os.path.exists(file.path):
            os.remove(file.path)
        db.session.delete(file)
    
    ProjectAccess.query.filter_by(project_id=project_id).delete()
    SharedLink.query.filter_by(project_id=project_id).delete()
    
    db.session.delete(project)
    db.session.commit()
    
    flash('Проект успешно удален!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/share/<token>')
def share(token):
    link = SharedLink.query.filter_by(token=token).first_or_404()
    project = Project.query.get_or_404(link.project_id)
    files = File.query.filter_by(project_id=project.id).all()
    
    users_with_access = []
    for access in project.access:
        user = User.query.get(access.user_id)
        if user:
            users_with_access.append({
                'id': user.id,
                'username': user.username,
                'access_level': access.access_level
            })
    
    return render_template('share.html', 
                          project=project, 
                          files=files,
                          users_with_access=users_with_access,
                          token=token)

@app.route('/generate_qr/<token>')
def generate_qr(token):
    share_url = f"{app.config['BASE_URL']}/share/{token}"
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(share_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({'qr_data': f'image/png;base64,{img_str}', 'url': share_url})

@app.route('/get_share_link/<int:project_id>')
@login_required
def get_share_link(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    link = SharedLink.query.filter_by(project_id=project_id).first()
    if not link:
        token = str(uuid.uuid4())
        link = SharedLink(token=token, project_id=project_id)
        db.session.add(link)
        db.session.commit()
    
    share_url = f"{app.config['BASE_URL']}/share/{link.token}"
    return jsonify({'url': share_url, 'token': link.token})

@app.route('/project/<int:project_id>/users')
@login_required
def project_users(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    users_with_access = []
    for access in project.access:
        user = User.query.get(access.user_id)
        if user:
            users_with_access.append({
                'id': user.id,
                'username': user.username,
                'access_level': access.access_level
            })
    
    return jsonify({'users': users_with_access})

@app.route('/project/<int:project_id>/grant-access', methods=['POST'])
@login_required
def grant_access(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    username = request.form['username']
    access_level = request.form['access_level']
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    existing_access = ProjectAccess.query.filter_by(project_id=project_id, user_id=user.id).first()
    if existing_access:
        return jsonify({'error': 'User already has access'}), 400
    
    new_access = ProjectAccess(project_id=project_id, user_id=user.id, access_level=access_level)
    db.session.add(new_access)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/project/<int:project_id>/revoke-access/<int:user_id>', methods=['POST'])
@login_required
def revoke_access(project_id, user_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    access = ProjectAccess.query.filter_by(project_id=project_id, user_id=user_id).first()
    if not access:
        return jsonify({'error': 'User does not have access'}), 404
    
    db.session.delete(access)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/get_all_users')
@login_required
def get_all_users():
    users = User.query.filter(User.id != current_user.id).all()
    users_list = [{'id': user.id, 'username': user.username} for user in users]
    return jsonify({'users': users_list})

def format_size(bytes):
    if bytes >= 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024 * 1024):.2f} ГБ"
    elif bytes >= 1024 * 1024:
        return f"{bytes / (1024 * 1024):.2f} МБ"
    elif bytes >= 1024:
        return f"{bytes / 1024:.2f} КБ"
    else:
        return f"{bytes} Б"

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
