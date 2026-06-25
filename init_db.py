from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
import os
import json
from datetime import datetime
import uuid

# 数据库配置（与backend.py保持一致）
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zhihuiqingchun.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

db = SQLAlchemy(app)

# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 数据库模型（与backend.py保持一致）
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联
    files = db.relationship('UserFile', backref='user', lazy=True, cascade='all, delete-orphan')
    history_records = db.relationship('HistoryRecord', backref='user', lazy=True, cascade='all, delete-orphan')

class UserFile(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联
    history_records = db.relationship('HistoryRecord', backref='file', lazy=True, cascade='all, delete-orphan')

class HistoryRecord(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    file_id = db.Column(db.String(36), db.ForeignKey('user_file.id'), nullable=True)
    record_type = db.Column(db.String(50), nullable=False)  # 'analysis', 'report', 'quiz'
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)  # JSON字符串存储详细内容
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def init_database():
    """初始化数据库"""
    print("正在初始化数据库...")
    
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("✓ 数据库表已创建")
        
        # 创建默认管理员用户（可选）
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@zhihuiqingchun.com',
                password_hash=generate_password_hash('admin123')
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✓ 默认管理员用户已创建 (用户名: admin, 密码: admin123)")
        
        print("数据库初始化完成！")

def reset_database():
    """重置数据库（删除所有数据）"""
    print("正在重置数据库...")
    
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("✓ 数据库已重置")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'reset':
        reset_database()
    else:
        init_database()