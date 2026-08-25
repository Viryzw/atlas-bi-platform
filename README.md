### Atlas-BI-Platform

> 西北工业大学 1班 6组

---

##### 〇、环境配置

（1）数据库创建

```bash
# 登陆数据库
mysql -h 127.0.0.1 -P 3306 -u <MySQL用户名> -p

# 创建数据库
CREATE DATABASE IF NOT EXISTS bi_platform
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

（2）数据库持久化配置：连接与加密

```bash
cd backend
touch .env.production
chmod 600 .env.production

# 配置内容如下
export DATABASE_URL='mysql+pymysql://你的MySQL用户名:你的MySQL密码@127.0.0.1:3306/bi_platform?charset=utf8mb4'
export AUTH_SECRET='第一次生成的密钥' # openssl rand -hex 32
export ATLAS_SECRET_KEY='第二次生成的密钥' # openssl rand -hex 32
export HOST='0.0.0.0'
export PORT='8000'
export APP_RELOAD='false'
```

（3）Python 依赖

```bash
conda create -n BI python=3.12
conda activate BI
pip install -r requirements.txt
```

（4）模型配置：从 [models]( https://drive.google.com/file/d/12jDw7-7ly_CGxuwz6bLcZNlMXBV0btyG/view?usp=share_link) 下载模型后解压至 `backend/`

---

##### 一、启动平台

（1）启动后端

```bash
conda activate BI
cd backend/
set -a
source .env.production
set +a
python main.py
```

（2）启动前端

```bash
npm install
npm run dev
```

（3）本地访问：[点击前往](https://127.0.0.1:5173)

