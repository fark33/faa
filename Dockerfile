FROM python:3.10-slim

WORKDIR /app

# نصب ابزارهای مورد نیاز سیستم‌عامل
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# کپی و نصب پکیج‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن بقیه فایل‌های پروژه به داخل کانتینر
COPY . .

# اجرای ربات
CMD ["python", "bot.py"]
