import os
import time
import asyncio
from telegram import Bot

TOKEN = ""
CHAT_ID = ""

root_path = "/sdcard"

extensions = ('.jpg', '.jpeg', '.png', '.webp',
              '.mp4', '.mkv', '.mov')

MAX_SIZE = 50 * 1024 * 1024  # 50MB bot limit
progress_file = "progress.txt"
skipped_files = []

async def main():
    bot = Bot(token=TOKEN)

    start_index = 0
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            start_index = int(f.read().strip())

    all_files = []

    print("Scanning storage...")

    for root, dirs, files in os.walk(root_path):
        for file in files:
            if file.lower().endswith(extensions):
                full_path = os.path.join(root, file)
                all_files.append(full_path)

    print(f"Total files found: {len(all_files)}")
    print(f"Resuming from index: {start_index}")

    batch_size = 20

    for i in range(start_index, len(all_files), batch_size):
        batch = all_files[i:i+batch_size]

        for file_path in batch:
            try:
                file_size = os.path.getsize(file_path)

                if file_size > MAX_SIZE:
                    skipped_files.append(f"{file_path} (Too Large)")
                    continue

                with open(file_path, 'rb') as f:
                    if file_path.lower().endswith(('.mp4', '.mkv', '.mov')):
                        await bot.send_video(chat_id=CHAT_ID, video=f)
                    else:
                        await bot.send_photo(chat_id=CHAT_ID, photo=f)

                print(f"Sent: {file_path}")

            except Exception as e:
                skipped_files.append(f"{file_path} (Error: {e})")

        with open(progress_file, "w") as f:
            f.write(str(i + batch_size))

        await asyncio.sleep(10)

    if skipped_files:
        print("\nSkipped Files:")
        for file in skipped_files:
            print(file)

    print("\nAll Done 🚀")

asyncio.run(main())
