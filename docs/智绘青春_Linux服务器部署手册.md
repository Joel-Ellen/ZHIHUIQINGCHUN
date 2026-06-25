# 智绘青春 - Linux 服务器完整部署手册

> **适用系统**：Alibaba Cloud Linux 3 / CentOS 8 / RHEL 8 / Anolis 8 系列（RPM/YUM 系发行版）
>
> **项目概述**：智绘青春是一款基于 Flask 后端 + 单页前端（React CDN）的智能职业规划系统，集成知识图谱、LSH+FAISS 混合检索、GNN 图神经网络、Agentic RAG 等高级功能。
>
> **部署方式**：前后端一体部署（Flask 同时提供 API 接口和静态文件服务）

---

## 目录

1. [服务器环境要求](#1-服务器环境要求)
2. [上传项目到服务器](#2-上传项目到服务器)
3. [服务器环境配置](#3-服务器环境配置)
4. [Python 虚拟环境搭建](#4-python-虚拟环境搭建)
5. [安装项目依赖](#5-安装项目依赖)
6. [项目配置检查与修改](#6-项目配置检查与修改)
7. [初始化数据与索引](#7-初始化数据与索引)
8. [启动服务（开发/测试模式）](#8-启动服务开发测试模式)
9. [生产环境部署（Gunicorn + Nginx）](#9-生产环境部署gunicorn--nginx)
10. [Systemd 进程守护配置](#10-systemd-进程守护配置)
11. [域名与 SSL 证书配置](#11-域名与-ssl-证书配置)
12. [防火墙与安全组配置](#12-防火墙与安全组配置)
13. [SELinux 配置（重要）](#13-selinux-配置重要)
14. [常见问题排查](#14-常见问题排查)
15. [维护与更新](#15-维护与更新)

---

## 1. 服务器环境要求

### 1.1 硬件建议

| 配置项 | 最低要求 | 推荐配置 |
|--------|----------|----------|
| CPU | 2 核 | 4 核及以上 |
| 内存 | 4 GB | 8 GB 及以上（PyTorch 模型加载需要较多内存） |
| 磁盘 | 20 GB SSD | 50 GB SSD |
| 带宽 | 3 Mbps | 5 Mbps 及以上 |

### 1.2 操作系统

- **本文档针对**：Alibaba Cloud Linux 3 (OpenAnolis Edition) / CentOS 8 / RHEL 8 / Anolis 8
- **包管理器**：`yum` / `dnf`（RPM 系）

### 1.3 必备软件

```bash
# 检查系统版本
cat /etc/os-release

# 更新系统软件包
sudo yum update -y
# 或
sudo dnf update -y

# 安装基础工具组
sudo yum groupinstall -y "Development Tools"

# 安装基础工具
sudo yum install -y \
    curl \
    wget \
    vim \
    git \
    unzip \
    tar \
    gcc \
    gcc-c++ \
    make \
    openssl-devel \
    bzip2-devel \
    libffi-devel \
    zlib-devel \
    readline-devel \
    sqlite-devel \
    nginx

# 检查 Python 版本（Alibaba Cloud Linux 3 默认带 Python 3.9）
python3 --version   # 应显示 3.9.x
pip3 --version
```

> **注意**：本项目依赖 PyTorch、FAISS 等深度学习库，**强烈建议使用 Python 3.9 或 3.10**，Python 3.12 可能存在部分库兼容性问题。
> 
> Alibaba Cloud Linux 3 默认提供 Python 3.9，无需额外安装。

---

## 2. 上传项目到服务器

### 2.1 方式一：使用 scp / rsync（推荐）

**在本地电脑（Windows PowerShell / macOS Terminal / Linux Terminal）执行：**

```bash
# ====== 方法 A：使用 scp ======
# 将整个项目文件夹上传到服务器的 /home 目录下
# 替换 your-server-ip 为你的服务器公网 IP
scp -r C:\Users\17873\Desktop\2026049861-参赛总文件夹\2026049861-02素材与源码\zhihuiqingchun root@your-server-ip:/home/

# 如果使用密钥登录（阿里云推荐）
scp -r -i ~/.ssh/your-key.pem C:\Users\17873\Desktop\zhihuiqingchun root@your-server-ip:/home/


# ====== 方法 B：使用 rsync（支持断点续传，推荐大文件）======
# Windows 需先安装 rsync（通过 Git Bash 或 WSL）
rsync -avz --progress \
  /mnt/c/Users/17873/Desktop/2026049861-参赛总文件夹/2026049861-02素材与源码/zhihuiqingchun/ \
  root@your-server-ip:/home/zhihuiqingchun/
```

### 2.2 方式二：使用 Git（如果项目已在 Git 仓库）

```bash
# 在服务器上执行
sudo mkdir -p /home/zhihuiqingchun
cd /home/zhihuiqingchun
git clone https://github.com/your-repo/zhihuiqingchun.git .
```

### 2.3 方式三：使用 SFTP 客户端（图形界面）

- **Windows 推荐**：FileZilla、WinSCP
- **macOS 推荐**：FileZilla、Cyberduck
- **连接信息**：
  - 主机：`your-server-ip`
  - 端口：`22`
  - 协议：SFTP
  - 用户名：`root`（或你的普通用户名）
  - 密码/密钥：你的登录凭证（阿里云通常使用密钥对）

### 2.4 上传后检查

```bash
# SSH 登录到服务器（阿里云默认用户可能是 root 或 ecs-user）
ssh root@your-server-ip
# 或
ssh ecs-user@your-server-ip

# 检查上传是否成功
cd /home/zhihuiqingchun
ls -la

# 预期看到的文件结构：
# backend.py
# index.html
# api.js
# backend/
# jobs_data.json
# job_profiles.json
# requirements.txt
# uploads/ (如不存在会自动创建)
```

---

## 3. 服务器环境配置

### 3.1 创建工作目录并设置权限

```bash
sudo mkdir -p /home/zhihuiqingchun
cd /home/zhihuiqingchun

# 设置目录权限（以 root 用户为例；如使用普通用户请替换）
sudo chown -R root:root /home/zhihuiqingchun
chmod -R 755 /home/zhihuiqingchun
```

### 3.2 Python 3.9 环境（Alibaba Cloud Linux 3 已内置）

```bash
# 检查默认 Python3 版本
python3 --version
# 输出应为：Python 3.9.x

# 安装 pip 和 venv（如未安装）
sudo yum install -y python3-pip python3-venv python3-devel

# 升级 pip
python3 -m pip install --upgrade pip setuptools wheel
```

> 如需安装 Python 3.10/3.11，可使用 Anaconda 或从源码编译，但 3.9 已足够运行本项目。

### 3.3 安装系统级依赖（PyTorch/FAISS 需要）

```bash
sudo yum install -y \
    openblas-devel \
    libgomp \
    libffi-devel \
    python3-devel
```

### 3.4 安装 Nginx

```bash
# Alibaba Cloud Linux 3 / CentOS 8
sudo yum install -y nginx

# 启动 Nginx 并设置开机自启
sudo systemctl start nginx
sudo systemctl enable nginx

# 查看 Nginx 状态
sudo systemctl status nginx
```

---

## 4. Python 虚拟环境搭建

> **强烈建议使用虚拟环境**，避免与系统 Python 包冲突。

```bash
cd /home/zhihuiqingchun

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 激活后，命令行提示符前会出现 (venv)
# 例如：(venv) [root@iZbp126i0wuvo4zh3mw3sfZ zhihuiqingchun]#

# 确认使用的是虚拟环境的 pip
which pip
# 应输出：/home/zhihuiqingchun/venv/bin/pip

# 升级 pip
pip install --upgrade pip setuptools wheel
```

> **重要**：后续所有 `pip install` 和 `python` 命令都必须在虚拟环境激活状态下执行！

---

## 5. 安装项目依赖

### 5.1 安装基础依赖

```bash
cd /home/zhihuiqingchun
source venv/bin/activate

# 先安装基础 Flask 依赖
pip install flask>=2.0.0 flask-cors>=3.0.0 requests>=2.25.0 flask-sqlalchemy>=3.0.0 werkzeug>=2.0.0 python-dotenv>=0.19.0
```

### 5.2 安装 PyTorch（按 CPU 版本）

> 服务器通常没有 NVIDIA GPU，安装 CPU 版本即可。如有 GPU，请参考 PyTorch 官网选择 CUDA 版本。

```bash
# CPU 版本（推荐，安装快，占用小）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 验证安装
python -c "import torch; print(torch.__version__)"
```

### 5.3 安装 FAISS（向量检索库）

```bash
# CPU 版本
pip install faiss-cpu>=1.7.4

# 验证安装
python -c "import faiss; print(faiss.__version__)"
```

### 5.4 安装其他 AI/ML 依赖

```bash
# 分步安装，便于排查问题

# 文本嵌入
pip install sentence-transformers>=2.2.0

# 图神经网络（安装可能较慢，依赖较多）
pip install torch-geometric>=2.3.0

# 图数据库驱动
pip install neo4j-python-driver>=5.0.0

# LSH 索引
pip install datasketch>=1.5.0

# 数值计算
pip install numpy>=1.24.0 scikit-learn>=1.3.0 scipy>=1.10.0

# 生产环境 WSGI 服务器（后面会用到）
pip install gunicorn
```

### 5.5 一键安装（如果上述分步安装没问题）

```bash
# 如果 requirements.txt 里的版本都兼容，可以直接：
pip install -r requirements.txt

# 但注意 requirements.txt 中 torch 和 faiss 可能需要单独安装 CPU 版本
```

### 5.6 验证所有依赖

```bash
python -c "
import flask
import flask_cors
import flask_sqlalchemy
import torch
import faiss
import numpy
import sklearn
import scipy
import sentence_transformers
import neo4j
import datasketch
print('✅ 所有核心依赖安装成功！')
"
```

---

## 6. 项目配置检查与修改

### 6.1 检查前端 API 地址（关键！）

```bash
cd /home/zhihuiqingchun
cat api.js | head -n 15
```

**确认第 8 行是：**
```javascript
let API_BASE_URL = '/api';
```

如果不是，请修改：
```bash
sed -i "s|let API_BASE_URL = 'http://localhost:5000/api';|let API_BASE_URL = '/api';|" api.js
```

### 6.2 检查后端数据库和上传目录配置

编辑 `backend.py`，确认以下配置符合服务器环境：

```bash
vim /home/zhihuiqingchun/backend.py
```

**重点关注（约第 33-43 行）：**

```python
# 数据库配置 - SQLite 文件会创建在项目根目录
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "zhihuiqingchun.db")}'

# 上传文件夹
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')

# 文件大小限制（16MB）
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
```

> 默认配置无需修改，但请确保 `/home/zhihuiqingchun` 目录有**写入权限**。

### 6.3 （可选）修改 SECRET_KEY

```python
# 第 36 行，生产环境务必修改！
app.config['SECRET_KEY'] = 'your-secret-key-here'
```

修改为随机字符串：
```bash
# 生成随机密钥
python3 -c "import secrets; print(secrets.token_hex(32))"

# 用生成的字符串替换 backend.py 中的 SECRET_KEY
sed -i "s/your-secret-key-here/$(python3 -c 'import secrets; print(secrets.token_hex(32))')/" backend.py
```

### 6.4 确保 uploads 目录可写

```bash
mkdir -p /home/zhihuiqingchun/uploads
chmod 755 /home/zhihuiqingchun/uploads
```

---

## 7. 初始化数据与索引

### 7.1 初始化数据库

```bash
cd /home/zhihuiqingchun
source venv/bin/activate

# 运行数据库初始化（Flask 会自动创建表）
python -c "
from backend import app, db
with app.app_context():
    db.create_all()
    print('数据库表创建成功！')
"
```

或者如果项目有 `init_db.py`：
```bash
python init_db.py
```

### 7.2 检查数据文件完整性

```bash
ls -la /home/zhihuiqingchun/*.json
ls -la /home/zhihuiqingchun/backend/data/

# 确认以下文件存在：
# jobs_data.json
# job_profiles.json
# backend/data/kg_graph.pkl
# backend/data/indices/faiss.index
# backend/data/indices/lsh_index.pkl
```

### 7.3 （可选）重建索引

如果索引文件损坏或需要重新构建：

```bash
cd /home/zhihuiqingchun
source venv/bin/activate

# 进入 scripts 目录执行构建脚本
cd backend/scripts
python build_indices.py
python build_kg.py
python build_gnn.py
```

---

## 8. 启动服务（开发/测试模式）

### 8.1 直接运行 Flask

```bash
cd /home/zhihuiqingchun
source venv/bin/activate

# 后台运行（使用 nohup）
nohup python backend.py > app.log 2>&1 &

# 查看运行状态
tail -f app.log

# 查看进程
ps aux | grep backend.py
```

### 8.2 测试访问

```bash
# 在服务器本地测试
curl http://127.0.0.1:5000/api/health

# 预期返回：
# {"status": "ok", ...}

# 测试前端页面
curl -I http://127.0.0.1:5000/
```

### 8.3 从外网访问测试

在浏览器中访问：
```
http://your-server-ip:5000/
```

> **注意**：需要先在防火墙中开放 5000 端口（见第 12 章）。

### 8.4 停止服务

```bash
# 找到进程 ID 并杀死
ps aux | grep backend.py
kill <PID>

# 或者强制停止
pkill -f backend.py
```

---

## 9. 生产环境部署（Gunicorn + Nginx）

> **开发测试完成后，强烈建议使用此方案部署到生产环境。**
>
> - Gunicorn：Python WSGI HTTP 服务器，性能更好
> - Nginx：反向代理 + 静态文件加速 + 负载均衡

### 9.1 使用 Gunicorn 启动 Flask

```bash
cd /home/zhihuiqingchun
source venv/bin/activate

# 测试启动（前台运行）
gunicorn -w 4 -b 127.0.0.1:8000 backend:app

# 参数说明：
# -w 4          : 4 个工作进程（建议 CPU 核心数 * 2 + 1）
# -b 127.0.0.1:8000 : 绑定到本地 8000 端口（Nginx 会反向代理过来）
# backend:app   : backend.py 中的 app 对象
```

如果启动成功，按 `Ctrl+C` 停止，继续配置 Systemd。

### 9.2 配置 Nginx 反向代理

> **CentOS / Alibaba Cloud Linux 与 Ubuntu 的差异**：
> Nginx 配置文件存放在 `/etc/nginx/conf.d/` 目录下（不是 `/etc/nginx/sites-available/`）。

```bash
# 创建 Nginx 配置文件
sudo vim /etc/nginx/conf.d/zhihuiqingchun.conf
```

**写入以下内容：**

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 如果没有域名，填写你的服务器公网 IP

    # 日志配置
    access_log /var/log/nginx/zhihuiqingchun_access.log;
    error_log /var/log/nginx/zhihuiqingchun_error.log;

    # 客户端最大上传大小（与 Flask 的 MAX_CONTENT_LENGTH 对应）
    client_max_body_size 16M;

    # 反向代理到 Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 静态文件缓存（可选优化）
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        proxy_pass http://127.0.0.1:8000;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

**启用配置：**

```bash
# CentOS / Alibaba Cloud Linux 无需创建符号链接，直接放在 conf.d 下即可加载

# 检查 Nginx 配置语法
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx

# 查看 Nginx 状态
sudo systemctl status nginx
```

> **注意**：如果 `nginx -t` 报错找不到目录 `/var/log/nginx/`，请手动创建：
> ```bash
> sudo mkdir -p /var/log/nginx
> sudo chown nginx:nginx /var/log/nginx
> ```

### 9.3 测试 Nginx 代理

```bash
# 确保 Gunicorn 正在运行（见第 10 章 Systemd 配置）

# 本地测试 Nginx 代理
curl http://127.0.0.1/api/health

# 外网访问（浏览器）
http://your-domain.com/
# 或
http://your-server-ip/
```

---

## 10. Systemd 进程守护配置

> 使用 Systemd 管理 Gunicorn，实现开机自启、自动重启、日志管理。

### 10.1 创建 Systemd 服务文件

```bash
sudo vim /etc/systemd/system/zhihuiqingchun.service
```

**写入以下内容（注意替换用户名）：**

```ini
[Unit]
Description=智绘青春 - 职业规划智能体
After=network.target

[Service]
# 运行用户和组（请替换为你的实际用户名，如 root、ecs-user 等）
User=root
Group=root

# 工作目录
WorkingDirectory=/home/zhihuiqingchun

# 虚拟环境的 Python 和 Gunicorn 路径
Environment="PATH=/home/zhihuiqingchun/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"

# 启动命令
ExecStart=/home/zhihuiqingchun/venv/bin/gunicorn \
    -w 4 \
    -b 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /home/zhihuiqingchun/logs/gunicorn_access.log \
    --error-logfile /home/zhihuiqingchun/logs/gunicorn_error.log \
    --capture-output \
    --enable-stdio-inheritance \
    backend:app

# 重启策略
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 10.2 创建日志目录

```bash
sudo mkdir -p /home/zhihuiqingchun/logs
sudo chown -R root:root /home/zhihuiqingchun/logs
# 如使用普通用户，请替换为：sudo chown -R ecs-user:ecs-user /home/zhihuiqingchun/logs
```

### 10.3 启动并启用服务

```bash
# 重新加载 Systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start zhihuiqingchun

# 设置开机自启
sudo systemctl enable zhihuiqingchun

# 查看状态
sudo systemctl status zhihuiqingchun

# 查看实时日志
sudo journalctl -u zhihuiqingchun -f

# 查看 Gunicorn 错误日志
tail -f /home/zhihuiqingchun/logs/gunicorn_error.log
```

### 10.4 常用管理命令

```bash
# 启动
sudo systemctl start zhihuiqingchun

# 停止
sudo systemctl stop zhihuiqingchun

# 重启（修改代码后使用）
sudo systemctl restart zhihuiqingchun

# 查看状态
sudo systemctl status zhihuiqingchun

# 查看日志
sudo journalctl -u zhihuiqingchun --no-pager -n 100
```

---

## 11. 域名与 SSL 证书配置

### 11.1 域名解析

在域名服务商处添加 A 记录：

| 记录类型 | 主机记录 | 记录值 |
|----------|----------|--------|
| A | @ | your-server-ip |
| A | www | your-server-ip |

### 11.2 使用 Certbot 申请免费 SSL 证书

```bash
# 安装 EPEL 源（Certbot 需要）
sudo yum install -y epel-release

# 安装 Certbot
sudo yum install -y certbot python3-certbot-nginx

# 申请证书（替换为你的域名）
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 按照提示操作，选择 redirect HTTP to HTTPS

# 测试自动续期
sudo certbot renew --dry-run
```

### 11.3 自动续期

Certbot 会自动配置定时任务，无需手动操作。如需检查：

```bash
sudo systemctl status certbot.timer
# 或查看 crontab
sudo cat /etc/crontab | grep certbot
```

### 11.4 Nginx SSL 配置示例（Certbot 会自动修改）

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

---

## 12. 防火墙与安全组配置

### 12.1 服务器防火墙（firewalld）

> **CentOS / Alibaba Cloud Linux 默认使用 firewalld**，不是 ufw。

```bash
# 查看防火墙状态
sudo systemctl status firewalld

# 如未运行，启动 firewalld
sudo systemctl start firewalld
sudo systemctl enable firewalld

# 查看已开放的端口
sudo firewall-cmd --list-all

# 允许 SSH（必须！否则可能无法连接服务器）
sudo firewall-cmd --permanent --add-service=ssh

# 允许 HTTP 和 HTTPS
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https

# 如果使用直接访问 Flask（测试时），允许 5000
sudo firewall-cmd --permanent --add-port=5000/tcp

# 重载防火墙配置
sudo firewall-cmd --reload

# 验证规则
sudo firewall-cmd --list-all
```

### 12.2 云服务器安全组（阿里云 ECS）

登录 **阿里云控制台 → ECS → 安全组**，添加以下入方向规则：

| 方向 | 协议类型 | 端口范围 | 授权对象 | 说明 |
|------|----------|----------|----------|------|
| 入方向 | 自定义 TCP | 22 | 0.0.0.0/0 | SSH |
| 入方向 | HTTP (80) | 80 | 0.0.0.0/0 | HTTP |
| 入方向 | HTTPS (443) | 443 | 0.0.0.0/0 | HTTPS |
| 入方向 | 自定义 TCP | 5000 | 0.0.0.0/0 | Flask 测试端口（可选，测试后删除） |

> **重要**：生产环境只开放 22、80、443，关闭 5000！

---

## 13. SELinux 配置（重要）

> **CentOS / Alibaba Cloud Linux 默认启用 SELinux**，可能会阻止 Nginx 连接本地 8000 端口，或阻止应用写入文件。

### 13.1 查看 SELinux 状态

```bash
getenforce
# 可能返回：Enforcing（强制模式）、Permissive（宽容模式）、Disabled（关闭）

# 详细查看
sestatus
```

### 13.2 方案 A：临时设置为宽容模式（快速测试）

```bash
sudo setenforce 0
getenforce
# 应返回：Permissive
```

> 重启后会恢复为 Enforcing，仅用于临时排查问题。

### 13.3 方案 B：允许 Nginx 网络连接（推荐生产环境）

```bash
# 允许 Nginx 连接后端网络（代理到 127.0.0.1:8000）
sudo setsebool -P httpd_can_network_connect 1

# 允许 Nginx 作为反向代理
sudo setsebool -P httpd_can_network_relay 1

# 查看布尔值状态
getsebool httpd_can_network_connect
```

### 13.4 方案 C：配置项目目录的 SELinux 上下文

```bash
# 允许 Nginx 读取项目目录（如需要）
sudo chcon -R -t httpd_sys_content_t /home/zhihuiqingchun

# 允许写入 uploads 和数据库目录
sudo chcon -R -t httpd_sys_rw_content_t /home/zhihuiqingchun/uploads
sudo chcon -t httpd_sys_rw_content_t /home/zhihuiqingchun/zhihuiqingchun.db
```

### 13.5 方案 D：永久关闭 SELinux（不推荐，但最简单）

```bash
sudo vim /etc/selinux/config
```

修改为：
```ini
SELINUX=permissive
# 或
SELINUX=disabled
```

保存后**重启服务器**：
```bash
sudo reboot
```

---

## 14. 常见问题排查

### 14.1 前端页面显示正常，但 API 调用失败

**现象**：页面能打开，但点击功能按钮无反应，F12 Console 报网络错误。

**排查步骤**：

```bash
# 1. 检查 api.js 中的 API_BASE_URL
grep "API_BASE_URL" /home/zhihuiqingchun/api.js
# 应为：let API_BASE_URL = '/api';

# 2. 检查后端是否运行
curl http://127.0.0.1:8000/api/health

# 3. 检查 Nginx 代理是否正常
sudo nginx -t
sudo systemctl status nginx

# 4. 查看 Nginx 错误日志
tail -f /var/log/nginx/zhihuiqingchun_error.log
# 或
sudo journalctl -u nginx -f

# 5. 检查 SELinux 是否阻止了连接
getenforce
sudo cat /var/log/audit/audit.log | grep nginx | tail -20
```

### 14.2 上传文件失败

**排查**：
```bash
# 检查 uploads 目录权限
ls -la /home/zhihuiqingchun/uploads
chmod 755 /home/zhihuiqingchun/uploads
chown -R root:root /home/zhihuiqingchun/uploads

# 检查 SELinux 是否阻止写入
ls -Z /home/zhihuiqingchun/uploads
sudo chcon -R -t httpd_sys_rw_content_t /home/zhihuiqingchun/uploads

# 检查 Nginx 的 client_max_body_size
grep client_max_body_size /etc/nginx/conf.d/zhihuiqingchun.conf
# 应不小于 Flask 中的 MAX_CONTENT_LENGTH (16M)
```

### 14.3 依赖安装失败（特别是 torch/faiss）

**解决方案**：
```bash
# 单独安装 CPU 版本
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install faiss-cpu

# 如果仍失败，尝试指定版本
pip install torch==2.1.0+cpu --index-url https://download.pytorch.org/whl/cpu
pip install faiss-cpu==1.7.4

# 内存不足导致安装失败（服务器内存 < 4GB）
# 解决方案：增加 swap 空间
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 让 swap 永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 14.4 数据库锁定或权限错误

```bash
# 检查数据库文件权限
ls -la /home/zhihuiqingchun/zhihuiqingchun.db
ls -Z /home/zhihuiqingchun/zhihuiqingchun.db

chown root:root /home/zhihuiqingchun/zhihuiqingchun.db
chmod 644 /home/zhihuiqingchun/zhihuiqingchun.db
sudo chcon -t httpd_sys_rw_content_t /home/zhihuiqingchun/zhihuiqingchun.db

# 如果数据库被锁定，重启服务
sudo systemctl restart zhihuiqingchun
```

### 14.5 503 Service Unavailable

```bash
# Gunicorn 未运行或崩溃
sudo systemctl status zhihuiqingchun
sudo journalctl -u zhihuiqingchun --no-pager -n 50

# 检查端口是否被占用
sudo ss -tlnp | grep 8000
sudo lsof -i :8000

# 检查 SELinux
getenforce
sudo ausearch -m avc -ts recent | grep gunicorn
```

### 14.6 中文乱码

```bash
# 检查系统 locale
locale

# 安装中文语言包
sudo yum install -y glibc-langpack-zh

# 设置 UTF-8
export LANG=zh_CN.UTF-8
export LC_ALL=zh_CN.UTF-8

# 添加到 ~/.bashrc
echo 'export LANG=zh_CN.UTF-8' >> ~/.bashrc
echo 'export LC_ALL=zh_CN.UTF-8' >> ~/.bashrc
source ~/.bashrc

# 验证
locale
```

### 14.7 内存不足导致进程被 Kill

```bash
# 查看内存使用
free -h

# 查看 OOM Kill 记录
dmesg | grep -i "killed process"
journalctl -k | grep -i "out of memory"

# 解决方案：
# 1. 增加服务器内存
# 2. 减少 Gunicorn 工作进程数（-w 2 代替 -w 4）
# 3. 增加 Swap
sudo swapon --show
```

### 14.8 Nginx 403 Forbidden 错误

```bash
# 检查 Nginx 用户是否能访问项目目录
ps aux | grep nginx
# 查看 nginx 运行用户（通常是 nginx）

# 确保目录权限正确
chmod 755 /home/zhihuiqingchun
chmod 755 /home

# 检查 SELinux
getenforce
sudo chcon -R -t httpd_sys_content_t /home/zhihuiqingchun
```

### 14.9 Nginx 配置文件位置说明

> **CentOS / Alibaba Cloud Linux 与 Ubuntu 的重要区别**：

| 项目 | CentOS / Alibaba Cloud Linux | Ubuntu |
|------|------------------------------|--------|
| 站点配置目录 | `/etc/nginx/conf.d/` | `/etc/nginx/sites-available/` |
| 主配置文件 | `/etc/nginx/nginx.conf` | `/etc/nginx/nginx.conf` |
| 默认站点 | `/etc/nginx/conf.d/default.conf` | `/etc/nginx/sites-enabled/default` |
| 日志目录 | `/var/log/nginx/` | `/var/log/nginx/` |
| Nginx 用户 | `nginx` | `www-data` |

---

## 15. 维护与更新

### 15.1 更新项目代码

```bash
cd /home/zhihuiqingchun

# 如果使用了 Git
git pull origin main

# 如果是手动上传，重新 scp/rsync 上传后：
# 重启服务
sudo systemctl restart zhihuiqingchun
sudo systemctl restart nginx
```

### 15.2 备份数据

```bash
# 备份数据库和上传的文件
tar -czvf backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    /home/zhihuiqingchun/zhihuiqingchun.db \
    /home/zhihuiqingchun/uploads/ \
    /home/zhihuiqingchun/*.json \
    /home/zhihuiqingchun/backend/data/

# 定时备份（添加到 crontab）
crontab -e
# 添加：0 3 * * * tar -czvf /home/backups/zhihuiqingchun_$(date +\%Y\%m\%d).tar.gz /home/zhihuiqingchun/zhihuiqingchun.db /home/zhihuiqingchun/uploads/
```

### 15.3 查看系统资源占用

```bash
# 查看 CPU/内存占用
top
# 或更友好的
yum install -y htop
htop

# 查看磁盘空间
df -h

# 查看 Gunicorn 进程
ps aux | grep gunicorn
```

### 15.4 日志清理

```bash
# 手动清理旧日志
find /home/zhihuiqingchun/logs -name "*.log" -mtime +30 -delete
find /var/log/nginx -name "*.log.*" -mtime +30 -delete
find /var/log/journal -name "*.journal*" -mtime +30 -delete

# 清理 journal 日志
sudo journalctl --vacuum-time=7d
```

---

## 附录 A：快速检查清单

部署完成后，逐项确认：

- [ ] 项目文件已上传到 `/home/zhihuiqingchun`
- [ ] Python 虚拟环境已创建并激活
- [ ] 所有依赖安装成功（`pip list` 检查）
- [ ] `api.js` 中的 `API_BASE_URL` 为 `/api`
- [ ] `backend.py` 的 `SECRET_KEY` 已修改
- [ ] `uploads/` 目录存在且有写入权限
- [ ] 数据库初始化成功
- [ ] Gunicorn 能正常启动
- [ ] Nginx 配置正确且已 reload
- [ ] Nginx 日志目录存在且权限正确
- [ ] Systemd 服务已启用并运行
- [ ] firewalld 放行 http、https 服务（及 5000 测试端口）
- [ ] 阿里云安全组放行 22、80、443 端口
- [ ] SELinux 已配置（或已设为 permissive）
- [ ] 浏览器访问 `http://your-server-ip/` 正常
- [ ] API 接口测试通过（`curl http://your-server-ip/api/health`）
- [ ] 文件上传功能正常
- [ ] （可选）域名解析和 SSL 证书配置完成

---

## 附录 B：目录结构速查

```
/home/zhihuiqingchun/
├── venv/                       # Python 虚拟环境
├── logs/                       # 日志目录
│   ├── gunicorn_access.log
│   └── gunicorn_error.log
├── uploads/                    # 用户上传文件
├── backend/                    # 后端模块
│   ├── data/
│   │   ├── indices/            # FAISS/LSH 索引
│   │   ├── models/             # GNN 模型文件
│   │   └── vectors/            # 向量数据
│   ├── services/               # 业务服务
│   ├── utils/                  # 工具类
│   └── scripts/                # 构建脚本
├── backend.py                  # Flask 主入口
├── index.html                  # 前端页面
├── api.js                      # 前端 API 模块
├── jobs_data.json              # 岗位数据
├── job_profiles.json           # 岗位画像数据
├── requirements.txt            # Python 依赖
└── zhihuiqingchun.db           # SQLite 数据库（运行后生成）
```

---

## 附录 C：CentOS / Alibaba Cloud Linux 与 Ubuntu 命令对照表

| 操作 | CentOS / Alibaba Cloud Linux | Ubuntu |
|------|------------------------------|--------|
| 包管理器 | `yum` / `dnf` | `apt` |
| 更新系统 | `sudo yum update -y` | `sudo apt update && sudo apt upgrade -y` |
| 安装软件 | `sudo yum install -y nginx` | `sudo apt install -y nginx` |
| Nginx 配置目录 | `/etc/nginx/conf.d/` | `/etc/nginx/sites-available/` |
| Nginx 用户 | `nginx` | `www-data` |
| 防火墙 | `firewalld` | `ufw` |
| 开放端口 | `firewall-cmd --add-port=80/tcp` | `ufw allow 80/tcp` |
| SELinux | 默认启用 | 默认禁用 |
| Python 默认版本 | 3.9 (Alibaba Cloud Linux 3) | 3.10 (Ubuntu 22.04) |

---

**部署完成！🎉**

如有问题，请按第 14 章排查步骤依次检查，或查看各组件日志定位问题。
