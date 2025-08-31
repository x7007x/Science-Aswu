from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import redis
import requests
import json
import uuid
from datetime import datetime
from functools import wraps
import g4f

app = Flask(__name__)
app.secret_key = 'aswan-university-science-faculty-2024'

r = redis.Redis(
    host='redis-13822.c15.us-east-1-2.ec2.redns.redis-cloud.com',
    port=13822,
    decode_responses=True,
    username="default",
    password="Y5cUI9VBRjbOG4DhPStJE5hWbD9coyNS",
)

def upload_to_catbox(file_stream, filename='file'):
    url = "https://catbox.moe/user/api.php"
    payload = {'reqtype': 'fileupload', 'userhash': ''}
    files = [('fileToUpload', (filename, file_stream, 'application/octet-stream'))]
    headers = {'User-Agent': "Mozilla/5.0"}
    try:
        response = requests.post(url, data=payload, files=files, headers=headers)
        response.raise_for_status()
        return response.text
    except:
        return None

def upload_multiple_files(files):
    uploaded_files = []
    for file in files:
        if file.filename:
            url = upload_to_catbox(file.stream, file.filename)
            if url:
                file_type = 'image'
                if file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.webm')):
                    file_type = 'video'
                elif not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    file_type = 'file'
                
                uploaded_files.append({
                    'url': url,
                    'type': file_type,
                    'filename': file.filename
                })
    return uploaded_files

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_phone' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_phone(phone):
    user_data = r.get(f"user:{phone}")
    if user_data:
        return json.loads(user_data)
    return None

def create_user(phone, password, name):
    user_data = {
        'phone': phone,
        'password': password,
        'name': name,
        'created_at': datetime.now().isoformat()
    }
    r.set(f"user:{phone}", json.dumps(user_data))
    return user_data

def get_all_entries():
    entry_keys = r.keys("entry:*")
    entries = []
    for key in entry_keys:
        entry_data = r.get(key)
        if entry_data:
            entry = json.loads(entry_data)
            entries.append(entry)
    return sorted(entries, key=lambda x: x.get('created_at', ''), reverse=True)

def get_entry(entry_id):
    entry_data = r.get(f"entry:{entry_id}")
    if entry_data:
        return json.loads(entry_data)
    return None

def save_entry(entry_data):
    r.set(f"entry:{entry_data['id']}", json.dumps(entry_data))

def delete_entry(entry_id):
    r.delete(f"entry:{entry_id}")

def init_admin():
    if not get_user_by_phone("010"):
        create_user("010", "010", "مدير النظام")

@app.route('/')
def index():
    entries = get_all_entries()
    search_query = request.args.get('search', '')
    if search_query:
        entries = [entry for entry in entries if 
                  search_query.lower() in entry['title'].lower() or 
                  search_query.lower() in entry['description'].lower()]
    return render_template('index.html', entries=entries, search_query=search_query)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        password = request.form['password']
        user = get_user_by_phone(phone)
        if user and user['password'] == password:
            session['user_phone'] = phone
            session['user_name'] = user['name']
            return redirect(url_for('admin'))
        flash('رقم الهاتف أو كلمة المرور غير صحيحة')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    entries = get_all_entries()
    return render_template('admin.html', entries=entries)

@app.route('/admin/create', methods=['GET', 'POST'])
@login_required
def create_entry():
    if request.method == 'POST':
        entry_id = str(uuid.uuid4())
        title = request.form['title']
        description = request.form['description']
        
        media_files = []
        if 'media' in request.files:
            files = request.files.getlist('media')
            media_files = upload_multiple_files(files)
        
        entry_data = {
            'id': entry_id,
            'title': title,
            'description': description,
            'media_files': media_files,
            'uploader_phone': session['user_phone'],
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'editor_phone': session['user_phone']
        }
        
        save_entry(entry_data)
        flash('تم إنشاء المحتوى بنجاح')
        return redirect(url_for('admin'))
    
    return render_template('create_entry.html')

@app.route('/admin/edit/<entry_id>', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    entry = get_entry(entry_id)
    if not entry:
        flash('المحتوى غير موجود')
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        entry['title'] = request.form['title']
        entry['description'] = request.form['description']
        entry['updated_at'] = datetime.now().isoformat()
        entry['editor_phone'] = session['user_phone']
        
        if 'media' in request.files:
            files = request.files.getlist('media')
            new_media = upload_multiple_files(files)
            if new_media:
                if 'media_files' not in entry:
                    entry['media_files'] = []
                entry['media_files'].extend(new_media)
        
        save_entry(entry)
        flash('تم تحديث المحتوى بنجاح')
        return redirect(url_for('admin'))
    
    return render_template('edit_entry.html', entry=entry)

@app.route('/admin/delete/<entry_id>')
@login_required
def delete_entry_route(entry_id):
    delete_entry(entry_id)
    flash('تم حذف المحتوى بنجاح')
    return redirect(url_for('admin'))

@app.route('/api/entries')
def api_entries():
    entries = get_all_entries()
    return jsonify(entries)

@app.route('/entry/<entry_id>')
def view_entry(entry_id):
    entry = get_entry(entry_id)
    if not entry:
        flash('المحتوى غير موجود')
        return redirect(url_for('index'))
    return render_template('view_entry.html', entry=entry)

@app.route('/api/chat', methods=['POST'])
def ai_chat():
    try:
        user_message = request.json.get('message', '')
        if not user_message:
            return jsonify({'error': 'لا يوجد رسالة'}), 400
        
        entries = get_all_entries()
        context = "المحتوى المتاح:\n"
        for entry in entries[:10]:
            context += f"- {entry['title']}: {entry['description'][:100]}...\n"
        
        response = g4f.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"أنت مساعد ذكي لطلاب كلية العلوم بجامعة أسوان. أسلوبك مرح، ودود، وبالعامية المصرية 100%. استخدم المعلومات التالية للإجابة على أسئلة الطلاب:\n{context}\nلو الطالب سأل عن حاجة مش موجودة عندك، اطلب منه يدخل الجروب ده ويسأل هناك بطريقة بسيطة ومفهومة:\nhttps://chat.whatsapp.com/CglJjN7sp3YJwFoyE0qH42?mode=ac_t"},
                {"role": "user", "content": user_message}
            ]
        )
        
        return jsonify({'response': response})
    except Exception as e:
        print(str(e))
        return jsonify({'error': 'حدث خطأ في الخدمة'}), 500

if __name__ == '__main__':
    #init_admin()
    app.run(debug=True)
