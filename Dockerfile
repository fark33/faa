FROM python:3.11-slim

# نصب ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# تنظیم پوشه کاری
WORKDIR /app

# کپی فایل پیش‌نیازها و نصب آن‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی تمام فایل‌های پروژه
COPY . .

# دستور اجرای ربات
CMD ["python", "bot.py"]
