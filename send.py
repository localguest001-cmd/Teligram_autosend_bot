import os
import time
import asyncio
from telegram import Bot
from telegram.error import RetryAfter, TimedOut, NetworkError, BadRequest, TelegramError

TOKEN = ""       # ← your bot token
CHAT_ID = ""     # ← your chat ID (or group/channel @username or -100xxxxxxxx)

root_path = "/sdcard"

extensions = ('.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mkv', '.mov')

MAX_SIZE = 50 * 1024 * 1024  # 50 MB
progress_file = "progress_v1.txt"
skipped_file  = "skipped.txt"    # only permanent skips + reason
sent_log_file = "upload_log.txt" # all successfully sent files (trace)

MAX_RETRIES = 3
BASE_SLEEP = 1.8               # safe delay between sends (1.8 s → \~33 files/min, no flood)

async def log_to_file(filename, msg, console=True):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"{timestamp} | {msg}\n"
    if console:
        print(line.strip())
    with open(filename, "a", encoding="utf-8") as f:
        f.write(line)

async def main():
    bot = Bot(token=TOKEN)

    # Load resume point
    start_index = 0
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r") as f:
                start_index = int(f.read().strip())
        except:
            start_index = 0

    # Scan all files
    all_files = []
    print("Scanning /sdcard for media files... (may take time)")
    for root, _, files in os.walk(root_path):
        for file in files:
            if file.lower().endswith(extensions):
                full_path = os.path.join(root, file)
                all_files.append(full_path)

    total = len(all_files)
    await log_to_file(sent_log_file, f"===== START / RESUME =====", console=True)
    await log_to_file(sent_log_file, f"Total files: {total} | Starting from index {start_index}", console=True)

    if start_index >= total:
        print("All files already processed.")
        return

    skipped = []

    for idx in range(start_index, total):
        file_path = all_files[idx]
        retries = 0
        success = False

        while retries < MAX_RETRIES and not success:
            try:
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    raise ValueError("Empty file (0 bytes)")
                if file_size > MAX_SIZE:
                    raise ValueError(f"File too large ({file_size//(1024*1024)} MB > 50 MB)")

                await log_to_file(sent_log_file,
                                  f"[{idx+1}/{total}] Attempting: {file_path} ({file_size//1024} KB)",
                                  console=True)

                with open(file_path, 'rb') as f:
                    if file_path.lower().endswith(('.mp4', '.mkv', '.mov')):
                        await bot.send_video(chat_id=CHAT_ID, video=f, supports_streaming=True)
                    else:
                        await bot.send_photo(chat_id=CHAT_ID, photo=f)

                # Success!
                success = True
                await log_to_file(sent_log_file,
                                  f"SENT SUCCESS: {file_path} (index {idx+1})",
                                  console=True)

            except RetryAfter as e:
                wait = e.retry_after + 3  # buffer
                await log_to_file(sent_log_file,
                                  f"FLOOD CONTROL → wait {wait}s (retry {retries+1}/{MAX_RETRIES})",
                                  console=True)
                await asyncio.sleep(wait)

            except (TimedOut, NetworkError) as e:
                await log_to_file(sent_log_file,
                                  f"Network/timeout → retry after 12s ({retries+1}/{MAX_RETRIES})",
                                  console=True)
                await asyncio.sleep(12)

            except BadRequest as e:
                err = str(e).lower()
                if any(x in err for x in ["invalid", "dimensions", "non-empty", "corrupt", "empty"]):
                    reason = f"Bad/invalid/corrupt file: {e}"
                    skipped.append(f"{file_path} ({reason})")
                    await log_to_file(skipped_file, f"{file_path} | {reason}", console=False)
                    await log_to_file(sent_log_file, f"SKIP (invalid): {file_path} → {reason}", console=True)
                    break  # no retry for bad files
                else:
                    await log_to_file(sent_log_file,
                                      f"BadRequest → retry after 6s: {e}",
                                      console=True)
                    await asyncio.sleep(6)

            except TelegramError as e:
                await log_to_file(sent_log_file,
                                  f"Telegram error → retry after 10s: {e}",
                                  console=True)
                await asyncio.sleep(10)

            except Exception as e:
                reason = f"Unexpected {type(e).__name__}: {e}"
                skipped.append(f"{file_path} ({reason})")
                await log_to_file(skipped_file, f"{file_path} | {reason}", console=False)
                await log_to_file(sent_log_file, f"SKIP (error): {file_path} → {reason}", console=True)
                break

            retries += 1
            if not success and retries < MAX_RETRIES:
                await asyncio.sleep(2)  # small extra pause between retries

        if success:
            # Save progress immediately after success
            with open(progress_file, "w") as f:
                f.write(str(idx + 1))
        else:
            # Max retries failed
            if file_path not in [s.split(" (")[0] for s in skipped]:
                reason = f"Failed after {MAX_RETRIES} retries"
                skipped.append(f"{file_path} ({reason})")
                await log_to_file(skipped_file, f"{file_path} | {reason}", console=False)
                await log_to_file(sent_log_file, f"SKIP (max retries): {file_path}", console=True)

        # Always delay between files (prevents flood)
        await asyncio.sleep(BASE_SLEEP)

    # Final summary
    await log_to_file(sent_log_file, "\n===== FINISHED =====", console=True)
    await log_to_file(sent_log_file, f"Processed: {total} files | Skipped/failed: {len(skipped)}", console=True)

    if skipped:
        await log_to_file(sent_log_file, "See skipped.txt for details", console=True)
        with open(skipped_file, "a", encoding="utf-8") as f:
            f.write("\n".join(skipped) + "\n")
    else:
        await log_to_file(sent_log_file, "All files sent! No skips.", console=True)

if __name__ == "__main__":
    asyncio.run(main())
